// Use dynamic API base from config.js, fallback to localhost for development
const API_BASE = window.CONFIG?.API_BASE || "http://127.0.0.1:8000";

// State
let currentPage = 1;
const ITEMS_PER_PAGE = 10;
let allFeedback = [];
let sentimentChart = null;
let categoryChart = null;

// Dark Mode
function initDarkMode() {
    const darkModeToggle = document.getElementById("dark-mode-toggle");
    const savedTheme = localStorage.getItem("theme");
    
    if (savedTheme === "dark") {
        document.body.classList.add("dark-mode");
    }
    
    darkModeToggle.addEventListener("click", () => {
        document.body.classList.toggle("dark-mode");
        const isDark = document.body.classList.contains("dark-mode");
        localStorage.setItem("theme", isDark ? "dark" : "light");
        
        // Recreate charts with new theme
        if (sentimentChart || categoryChart) {
            loadAnalytics();
        }
    });
}

// Toast Notification
function showToast(message, type = "success") {
    const toast = document.getElementById("toast");
    toast.textContent = message;
    toast.className = `toast ${type} show`;
    
    setTimeout(() => {
        toast.classList.remove("show");
    }, 3000);
}

// Submit Feedback Form
async function setupFeedbackForm() {
    const form = document.getElementById("feedback-form");
    const textarea = document.getElementById("feedback-text");
    const submitBtn = document.getElementById("submit-btn");
    const statusDiv = document.getElementById("submit-status");
    
    form.addEventListener("submit", async (e) => {
        e.preventDefault();
        
        const text = textarea.value.trim();
        if (!text) return;
        
        // Show loading
        submitBtn.disabled = true;
        submitBtn.querySelector(".btn-text").style.display = "none";
        submitBtn.querySelector(".btn-loader").style.display = "inline";
        statusDiv.className = "status-message";
        
        try {
            const response = await fetch(`${API_BASE}/feedback`, {
                method: "POST",
                headers: {"Content-Type": "application/json"},
                body: JSON.stringify({text})
            });
            
            if (!response.ok) throw new Error("Failed to submit");
            
            const result = await response.json();
            
            // Success
            textarea.value = "";
            statusDiv.className = "status-message success";
            statusDiv.textContent = `✅ Feedback submitted! Detected as ${result.sentiment} (${result.category}, ${result.priority} priority)`;
            showToast("Feedback submitted successfully!", "success");
            
            // Reload data
            setTimeout(() => {
                loadAnalytics();
                loadFeedback(getActiveFilters());
                statusDiv.style.display = "none";
            }, 2000);
            
        } catch (error) {
            statusDiv.className = "status-message error";
            statusDiv.textContent = "❌ Failed to submit feedback. Please try again.";
            showToast("Failed to submit feedback", "error");
        } finally {
            submitBtn.disabled = false;
            submitBtn.querySelector(".btn-text").style.display = "inline";
            submitBtn.querySelector(".btn-loader").style.display = "none";
        }
    });
}

// CSV Upload
async function setupCSVUpload() {
    const dropZone = document.getElementById("drop-zone");
    const fileInput = document.getElementById("file-input");
    const uploadStatus = document.getElementById("upload-status");
    
    // Drag and drop
    dropZone.addEventListener("dragover", (e) => {
        e.preventDefault();
        dropZone.classList.add("drag-over");
    });
    
    dropZone.addEventListener("dragleave", () => {
        dropZone.classList.remove("drag-over");
    });
    
    dropZone.addEventListener("drop", async (e) => {
        e.preventDefault();
        dropZone.classList.remove("drag-over");
        
        const file = e.dataTransfer.files[0];
        if (file && file.name.endsWith(".csv")) {
            await uploadCSV(file);
        } else {
            showToast("Please upload a CSV file", "error");
        }
    });
    
    // File input
    fileInput.addEventListener("change", async (e) => {
        const file = e.target.files[0];
        if (file) {
            await uploadCSV(file);
        }
    });
    
    async function uploadCSV(file) {
        uploadStatus.className = "status-message info";
        uploadStatus.textContent = `📤 Uploading ${file.name}... This may take a while with AI processing.`;
        
        const formData = new FormData();
        formData.append("file", file);
        
        try {
            const response = await fetch(`${API_BASE}/upload`, {
                method: "POST",
                body: formData
            });
            
            if (!response.ok) throw new Error("Upload failed");
            
            const result = await response.json();
            
            uploadStatus.className = "status-message success";
            uploadStatus.textContent = `✅ Successfully processed ${result.processed} feedback items!`;
            
            if (result.total_errors > 0) {
                uploadStatus.textContent += ` (${result.total_errors} errors)`;
            }
            
            showToast(`Processed ${result.processed} items!`, "success");
            
            // Reload data
            setTimeout(() => {
                loadAnalytics();
                loadFeedback(getActiveFilters());
            }, 1000);
            
        } catch (error) {
            uploadStatus.className = "status-message error";
            uploadStatus.textContent = "❌ Upload failed. Please check your CSV format.";
            showToast("Upload failed", "error");
        }
        
        fileInput.value = "";
    }
}

// Load analytics with charts
async function loadAnalytics() {
    try {
        const res = await fetch(`${API_BASE}/analytics`);
        const data = await res.json();

        const statsDiv = document.getElementById("stats");
        const insightDiv = document.getElementById("insight");

        // Render stats grid
        statsDiv.innerHTML = `
            <div class="stat-card">
                <div class="stat-value">${data.total_feedback}</div>
                <div class="stat-label">Total Feedback</div>
            </div>
            <div class="stat-card positive">
                <div class="stat-value">${data.sentiment_distribution.positive || 0}</div>
                <div class="stat-label">Positive</div>
            </div>
            <div class="stat-card negative">
                <div class="stat-value">${data.sentiment_distribution.negative || 0}</div>
                <div class="stat-label">Negative</div>
            </div>
            <div class="stat-card neutral">
                <div class="stat-value">${data.sentiment_distribution.neutral || 0}</div>
                <div class="stat-label">Neutral</div>
            </div>
        `;

        // Render category breakdown
        const categoryHTML = Object.entries(data.category_distribution)
            .map(([cat, count]) => `<span class="badge">${cat}: ${count}</span>`)
            .join(" ");

        // Render priority breakdown
        const priorityHTML = Object.entries(data.priority_distribution)
            .map(([pri, count]) => `<span class="badge priority-${pri}">${pri}: ${count}</span>`)
            .join(" ");

        statsDiv.innerHTML += `
            <div class="stat-card wide">
                <div class="stat-label">Categories</div>
                <div class="badges">${categoryHTML || 'No data'}</div>
            </div>
            <div class="stat-card wide">
                <div class="stat-label">Priorities</div>
                <div class="badges">${priorityHTML || 'No data'}</div>
            </div>
        `;

        // Render insight
        insightDiv.innerHTML = `
            <strong>💡 Insight:</strong> ${data.insight}
        `;
        
        // Render charts
        renderCharts(data);

    } catch (error) {
        console.error("Error loading analytics:", error);
        document.getElementById("stats").innerHTML = '<p class="error">Failed to load analytics</p>';
    }
}

// Render Charts
function renderCharts(data) {
    const isDark = document.body.classList.contains("dark-mode");
    const textColor = isDark ? "#e6e6e6" : "#333";
    const gridColor = isDark ? "#2a2a4e" : "#e0e0e0";
    
    // Sentiment Chart
    const sentimentCtx = document.getElementById("sentiment-chart");
    if (sentimentChart) sentimentChart.destroy();
    
    sentimentChart = new Chart(sentimentCtx, {
        type: "doughnut",
        data: {
            labels: ["Positive", "Negative", "Neutral"],
            datasets: [{
                data: [
                    data.sentiment_distribution.positive || 0,
                    data.sentiment_distribution.negative || 0,
                    data.sentiment_distribution.neutral || 0
                ],
                backgroundColor: [
                    "#4facfe",
                    "#fa709a",
                    "#a8edea"
                ],
                borderWidth: 2,
                borderColor: isDark ? "#16213e" : "#fff"
            }]
        },
        options: {
            responsive: true,
            plugins: {
                legend: {
                    labels: {color: textColor}
                }
            }
        }
    });
    
    // Category Chart
    const categoryCtx = document.getElementById("category-chart");
    if (categoryChart) categoryChart.destroy();
    
    categoryChart = new Chart(categoryCtx, {
        type: "bar",
        data: {
            labels: Object.keys(data.category_distribution),
            datasets: [{
                label: "Feedback Count",
                data: Object.values(data.category_distribution),
                backgroundColor: [
                    "#667eea",
                    "#764ba2",
                    "#f093fb",
                    "#f5576c"
                ],
                borderRadius: 8
            }]
        },
        options: {
            responsive: true,
            plugins: {
                legend: {display: false}
            },
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: {color: textColor},
                    grid: {color: gridColor}
                },
                x: {
                    ticks: {color: textColor},
                    grid: {color: gridColor}
                }
            }
        }
    });
}

// Load feedback with pagination
async function loadFeedback(filters = {}) {
    try {
        const params = new URLSearchParams();
        if (filters.category) params.append('category', filters.category);
        if (filters.sentiment) params.append('sentiment', filters.sentiment);
        if (filters.priority) params.append('priority', filters.priority);
        if (filters.source) params.append('source', filters.source);

        const queryString = params.toString();
        const url = `${API_BASE}/feedback${queryString ? '?' + queryString : ''}`;

        const res = await fetch(url);
        allFeedback = await res.json();

        const listEl = document.getElementById("feedback-list");
        const countEl = document.getElementById("feedback-count");
        const paginationEl = document.getElementById("pagination");
        
        countEl.textContent = `${allFeedback.length} items`;

        if (allFeedback.length === 0) {
            listEl.innerHTML = '<li class="empty">No feedback found</li>';
            paginationEl.style.display = "none";
            return;
        }
        
        // Pagination
        const totalPages = Math.ceil(allFeedback.length / ITEMS_PER_PAGE);
        const startIdx = (currentPage - 1) * ITEMS_PER_PAGE;
        const endIdx = startIdx + ITEMS_PER_PAGE;
        const pageItems = allFeedback.slice(startIdx, endIdx);
        
        listEl.innerHTML = "";
        
        pageItems.forEach(f => {
            const item = document.createElement("li");
            item.className = `feedback-item sentiment-${f.sentiment} priority-${f.priority}`;
            
            const date = new Date(f.created_at).toLocaleString();
            
            item.innerHTML = `
                <div class="feedback-header">
                    <span class="badge sentiment-${f.sentiment}">${f.sentiment}</span>
                    <span class="badge">${f.category}</span>
                    <span class="badge priority-${f.priority}">${f.priority}</span>
                    <span class="badge source-${f.source}">📍 ${f.source}</span>
                    <span class="timestamp">${date}</span>
                </div>
                <div class="feedback-text">${f.text}</div>
                <div class="feedback-meta">ID: ${f.id}</div>
            `;
            
            listEl.appendChild(item);
        });
        
        // Show/hide pagination
        if (totalPages > 1) {
            paginationEl.style.display = "flex";
            document.getElementById("page-info").textContent = `Page ${currentPage} of ${totalPages}`;
            document.getElementById("prev-page").disabled = currentPage === 1;
            document.getElementById("next-page").disabled = currentPage === totalPages;
        } else {
            paginationEl.style.display = "none";
        }

    } catch (error) {
        console.error("Error loading feedback:", error);
        document.getElementById("feedback-list").innerHTML = 
            '<li class="error">Failed to load feedback</li>';
    }
}

// Get active filters
function getActiveFilters() {
    return {
        category: document.getElementById("category-filter").value,
        sentiment: document.getElementById("sentiment-filter").value,
        priority: document.getElementById("priority-filter").value,
        source: document.getElementById("source-filter").value
    };
}

// Setup filters and pagination
function setupFilters() {
    const categoryFilter = document.getElementById("category-filter");
    const sentimentFilter = document.getElementById("sentiment-filter");
    const priorityFilter = document.getElementById("priority-filter");
    const sourceFilter = document.getElementById("source-filter");
    const resetButton = document.getElementById("reset-filters");
    const prevPage = document.getElementById("prev-page");
    const nextPage = document.getElementById("next-page");

    const applyFilters = () => {
        currentPage = 1;
        loadFeedback(getActiveFilters());
    };

    categoryFilter.addEventListener("change", applyFilters);
    sentimentFilter.addEventListener("change", applyFilters);
    priorityFilter.addEventListener("change", applyFilters);
    sourceFilter.addEventListener("change", applyFilters);

    resetButton.addEventListener("click", () => {
        categoryFilter.value = "";
        sentimentFilter.value = "";
        priorityFilter.value = "";
        sourceFilter.value = "";
        currentPage = 1;
        loadFeedback({});
        loadAnalytics();
    });
    
    // Pagination
    prevPage.addEventListener("click", () => {
        if (currentPage > 1) {
            currentPage--;
            loadFeedback(getActiveFilters());
        }
    });
    
    nextPage.addEventListener("click", () => {
        const totalPages = Math.ceil(allFeedback.length / ITEMS_PER_PAGE);
        if (currentPage < totalPages) {
            currentPage++;
            loadFeedback(getActiveFilters());
        }
    });
}

// Initial load
document.addEventListener("DOMContentLoaded", () => {
    initDarkMode();
    setupFeedbackForm();
    setupCSVUpload();
    loadAnalytics();
    loadFeedback({});
    setupFilters();

    // Auto-refresh every 30 seconds
    setInterval(() => {
        loadAnalytics();
        const currentFilters = getActiveFilters();
        loadFeedback(currentFilters);
    }, 30000);
});
