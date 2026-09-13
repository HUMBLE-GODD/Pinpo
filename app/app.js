/**
 * Pinpo Attorney Verification Viewer Client Script.
 * Renders structured Topic Index and full canonical transcript.
 * Provides interactive search, filtering, and line-level jump-and-highlight.
 */

document.addEventListener("DOMContentLoaded", () => {
    const data = window.DEPOSITION_DATA || { topics: [], lines: [] };
    const topicListEl = document.getElementById("topicList");
    const transcriptAreaEl = document.getElementById("transcriptArea");
    const searchInput = document.getElementById("searchInput");
    const activeTopicCountEl = document.getElementById("activeTopicCount");

    let activeTopicId = null;

    // Render Transcript
    function renderTranscript(lines) {
        transcriptAreaEl.innerHTML = "";
        
        // Group lines by page
        const pages = {};
        lines.forEach(l => {
            if (!pages[l.page]) pages[l.page] = [];
            pages[l.page].push(l);
        });

        Object.keys(pages).sort((a, b) => Number(a) - Number(b)).forEach(page => {
            const pageDiv = document.createElement("div");
            pageDiv.className = "page-container";
            pageDiv.id = `page-${page}`;

            const divider = document.createElement("div");
            divider.className = "page-divider";
            divider.textContent = `PAGE ${page}`;
            pageDiv.appendChild(divider);

            pages[page].forEach(l => {
                const lineDiv = document.createElement("div");
                lineDiv.className = "transcript-line";
                lineDiv.id = `line-${l.page}-${l.line}`;
                lineDiv.dataset.page = l.page;
                lineDiv.dataset.line = l.line;

                const numSpan = document.createElement("span");
                numSpan.className = "line-num";
                numSpan.textContent = l.line;

                const speakerSpan = document.createElement("span");
                speakerSpan.className = "line-speaker";
                speakerSpan.textContent = l.speaker ? `${l.speaker}:` : "";

                const textSpan = document.createElement("span");
                textSpan.className = "line-text";
                textSpan.textContent = l.text;

                const tsSpan = document.createElement("span");
                tsSpan.className = "line-ts";
                tsSpan.textContent = l.timestamp || "";

                lineDiv.appendChild(numSpan);
                if (l.speaker) lineDiv.appendChild(speakerSpan);
                lineDiv.appendChild(textSpan);
                if (l.timestamp) lineDiv.appendChild(tsSpan);

                pageDiv.appendChild(lineDiv);
            });

            transcriptAreaEl.appendChild(pageDiv);
        });
    }

    // Render Topics List
    function renderTopics(topics) {
        topicListEl.innerHTML = "";
        activeTopicCountEl.textContent = `${topics.length} topics`;

        topics.forEach((t, idx) => {
            const card = document.createElement("div");
            card.className = `topic-card ${activeTopicId === idx ? "active" : ""}`;
            card.id = `topic-card-${idx}`;

            const confPercent = Math.round((t.confidence || 0.85) * 100);

            card.innerHTML = `
                <div class="topic-header">
                    <span class="topic-title">${t.topic}</span>
                    <span class="topic-coord">P${t.start_page}:L${t.start_line} - P${t.end_page}:L${t.end_line}</span>
                </div>
                <div class="topic-summary">${t.summary || "Discussion of testimony."}</div>
                <div class="topic-footer">
                    <span class="confidence-badge">${confPercent}% Verified</span>
                    <span class="jump-btn">Jump to Source →</span>
                </div>
            `;

            card.addEventListener("click", () => {
                jumpToTopic(t, idx);
            });

            topicListEl.appendChild(card);
        });
    }

    // Jump to Topic & Highlight Lines
    function jumpToTopic(t, idx) {
        activeTopicId = idx;
        document.querySelectorAll(".topic-card").forEach(c => c.classList.remove("active"));
        const activeCard = document.getElementById(`topic-card-${idx}`);
        if (activeCard) activeCard.classList.add("active");

        // Clear existing highlights
        document.querySelectorAll(".transcript-line.highlighted").forEach(el => {
            el.classList.remove("highlighted", "highlighted-first", "highlighted-last");
        });

        // Highlight all rendered lines within the topic's page:line range.
        // This works correctly even when empty lines have been filtered out.
        let firstLineEl = null;
        let lastLineEl = null;
        const allLines = document.querySelectorAll(".transcript-line");
        allLines.forEach(el => {
            const p = Number(el.dataset.page);
            const l = Number(el.dataset.line);
            const afterStart = p > t.start_page || (p === t.start_page && l >= t.start_line);
            const beforeEnd = p < t.end_page || (p === t.end_page && l <= t.end_line);
            if (afterStart && beforeEnd) {
                el.classList.add("highlighted");
                if (!firstLineEl) {
                    firstLineEl = el;
                    el.classList.add("highlighted-first");
                }
                lastLineEl = el;
            }
        });
        if (lastLineEl) lastLineEl.classList.add("highlighted-last");

        // Scroll first line into view smoothly
        if (firstLineEl) {
            firstLineEl.scrollIntoView({ behavior: "smooth", block: "center" });
        }
    }

    // Keyword Search
    searchInput.addEventListener("input", (e) => {
        const query = e.target.value.toLowerCase().trim();
        if (!query) {
            renderTopics(data.topics);
            return;
        }
        const filtered = data.topics.filter(t => 
            t.topic.toLowerCase().includes(query) ||
            (t.summary && t.summary.toLowerCase().includes(query)) ||
            (t.supporting_quote && t.supporting_quote.toLowerCase().includes(query))
        );
        renderTopics(filtered);
    });

    // Update Header Metadata
    function updateHeaderMeta() {
        const witEl = document.getElementById("headerWitness");
        const matEl = document.getElementById("headerMatter");
        const dateEl = document.getElementById("headerDate");
        if (witEl && data.witness) witEl.textContent = data.witness;
        if (matEl && data.caseName) matEl.textContent = data.caseName;
        if (dateEl && data.date) dateEl.textContent = data.date;

        // Update transcript pane header with accurate line/page counts
        const transcriptHeader = document.getElementById("transcriptHeaderMeta");
        if (transcriptHeader && data.lines && data.lines.length > 0) {
            const pages = [...new Set(data.lines.map(l => l.page))].sort((a, b) => a - b);
            const minPage = pages[0];
            const maxPage = pages[pages.length - 1];
            const count = data.lines.length;
            transcriptHeader.textContent = `Pages ${minPage} - ${maxPage} | ${count.toLocaleString()} Canonical Lines`;
        }
    }

    // Dynamic Deposition JSON / JS Loader
    const loadBtn = document.getElementById("loadBtn");
    const loadDataInput = document.getElementById("loadDataInput");

    if (loadBtn && loadDataInput) {
        loadBtn.addEventListener("click", () => {
            loadDataInput.click();
        });

        loadDataInput.addEventListener("change", (e) => {
            const file = e.target.files[0];
            if (!file) return;

            const reader = new FileReader();
            reader.onload = (event) => {
                try {
                    const content = event.target.result;
                    let parsedData = null;
                    if (file.name.endsWith(".json")) {
                        const json = JSON.parse(content);
                        parsedData = {
                            title: json.title || "Custom Deposition",
                            witness: json.witness || "Custom Witness",
                            date: json.date || "Custom Date",
                            caseName: json.case_name || "Custom Matter",
                            topics: json.topics || [],
                            lines: json.lines || data.lines || []
                        };
                    } else if (file.name.endsWith(".js")) {
                        const match = content.match(/window\.DEPOSITION_DATA\s*=\s*(\{[\s\S]*\});/);
                        if (match) {
                            parsedData = JSON.parse(match[1]);
                        }
                    }
                    if (parsedData && parsedData.topics) {
                        data.title = parsedData.title;
                        data.witness = parsedData.witness;
                        data.date = parsedData.date;
                        data.caseName = parsedData.caseName;
                        data.topics = parsedData.topics;
                        if (parsedData.lines && parsedData.lines.length > 0) {
                            data.lines = parsedData.lines;
                        }
                        updateHeaderMeta();
                        renderTranscript(data.lines);
                        renderTopics(data.topics);
                    }
                } catch (err) {
                    alert("Failed to load deposition data: " + err.message);
                }
            };
            reader.readAsText(file);
        });
    }

    // PDF Upload Modal & Processing Logic
    const openUploadModalBtn = document.getElementById("openUploadModalBtn");
    const uploadModal = document.getElementById("uploadModal");
    const closeModalBtn = document.getElementById("closeModalBtn");
    const cancelModalBtn = document.getElementById("cancelModalBtn");
    const dropZone = document.getElementById("dropZone");
    const pdfFileInput = document.getElementById("pdfFileInput");
    const selectedFileName = document.getElementById("selectedFileName");
    const dropZoneText = document.getElementById("dropZoneText");
    const startUploadBtn = document.getElementById("startUploadBtn");
    const progressSection = document.getElementById("progressSection");
    const progressText = document.getElementById("progressText");
    const progressFill = document.getElementById("progressFill");
    const modalError = document.getElementById("modalError");

    const modeQuickLabel = document.getElementById("modeQuickLabel");
    const modeFullLabel = document.getElementById("modeFullLabel");

    let selectedPdfFile = null;

    if (openUploadModalBtn && uploadModal) {
        openUploadModalBtn.addEventListener("click", () => {
            uploadModal.style.display = "flex";
            resetModalState();
        });

        const hideModal = () => {
            uploadModal.style.display = "none";
            resetModalState();
        };

        if (closeModalBtn) closeModalBtn.addEventListener("click", hideModal);
        if (cancelModalBtn) cancelModalBtn.addEventListener("click", hideModal);

        // Radio card selection styling
        document.querySelectorAll('input[name="processMode"]').forEach(radio => {
            radio.addEventListener("change", (e) => {
                if (e.target.value === "quick") {
                    modeQuickLabel.classList.add("selected");
                    modeFullLabel.classList.remove("selected");
                } else {
                    modeFullLabel.classList.add("selected");
                    modeQuickLabel.classList.remove("selected");
                }
            });
        });

        // Drop zone interaction
        dropZone.addEventListener("click", () => {
            pdfFileInput.click();
        });

        dropZone.addEventListener("dragover", (e) => {
            e.preventDefault();
            dropZone.classList.add("dragover");
        });

        dropZone.addEventListener("dragleave", () => {
            dropZone.classList.remove("dragover");
        });

        dropZone.addEventListener("drop", (e) => {
            e.preventDefault();
            dropZone.classList.remove("dragover");
            if (e.dataTransfer.files.length > 0) {
                handleSelectedFile(e.dataTransfer.files[0]);
            }
        });

        pdfFileInput.addEventListener("change", (e) => {
            if (e.target.files.length > 0) {
                handleSelectedFile(e.target.files[0]);
            }
        });

        function handleSelectedFile(file) {
            if (!file.name.toLowerCase().endsWith(".pdf")) {
                showModalError("Please select a valid court reporter .pdf deposition file.");
                return;
            }
            selectedPdfFile = file;
            selectedFileName.textContent = `Selected: ${file.name} (${(file.size / 1024 / 1024).toFixed(2)} MB)`;
            selectedFileName.style.display = "inline-block";
            dropZoneText.style.display = "none";
            modalError.style.display = "none";
            startUploadBtn.disabled = false;
        }

        function resetModalState() {
            selectedPdfFile = null;
            if (selectedFileName) selectedFileName.style.display = "none";
            if (dropZoneText) dropZoneText.style.display = "block";
            if (startUploadBtn) startUploadBtn.disabled = true;
            if (progressSection) progressSection.style.display = "none";
            if (modalError) modalError.style.display = "none";
            if (pdfFileInput) pdfFileInput.value = "";
        }

        function showModalError(msg) {
            if (modalError) {
                modalError.textContent = msg;
                modalError.style.display = "block";
            }
            if (progressSection) progressSection.style.display = "none";
            if (startUploadBtn) startUploadBtn.disabled = false;
        }

        // Handle Upload & Process
        startUploadBtn.addEventListener("click", async () => {
            if (!selectedPdfFile) return;

            startUploadBtn.disabled = true;
            modalError.style.display = "none";
            progressSection.style.display = "block";

            const selectedMode = document.querySelector('input[name="processMode"]:checked')?.value || "full";
            const maxPages = selectedMode === "quick" ? 10 : 0;

            const steps = [
                "Uploading deposition to local pipeline server...",
                "Ingesting 25-line transcript grid with PyMuPDF...",
                "Detecting examination bounds & deponent metadata...",
                "Running Gemini semantic topic segmentation...",
                "Snapping line provenance & finalizing index..."
            ];

            let stepIdx = 0;
            const stepInterval = setInterval(() => {
                stepIdx = (stepIdx + 1) % steps.length;
                progressText.textContent = steps[stepIdx];
                progressFill.style.width = `${Math.min(95, 20 + stepIdx * 18)}%`;
            }, 2500);

            try {
                const formData = new FormData();
                formData.append("file", selectedPdfFile);
                formData.append("mode", selectedMode);
                formData.append("max_pages", String(maxPages));

                const response = await fetch("/api/upload", {
                    method: "POST",
                    body: formData
                });

                clearInterval(stepInterval);

                if (!response.ok) {
                    const errJson = await response.json().catch(() => ({}));
                    throw new Error(errJson.error || `Server responded with HTTP ${response.status}`);
                }

                const result = await response.json();
                progressFill.style.width = "100%";
                progressText.textContent = "Complete! Rendering topic navigator...";

                setTimeout(() => {
                    // Update global state
                    data.title = result.title;
                    data.witness = result.witness;
                    data.date = result.date;
                    data.caseName = result.caseName;
                    data.topics = result.topics;
                    data.lines = result.lines;

                    // Update UI
                    updateHeaderMeta();
                    renderTranscript(data.lines);
                    renderTopics(data.topics);
                    if (data.topics.length > 0) {
                        jumpToTopic(data.topics[0], 0);
                    }

                    hideModal();
                }, 600);

            } catch (err) {
                clearInterval(stepInterval);
                showModalError(`Processing error: ${err.message}. If running locally, start the backend with 'python3 server.py'.`);
            }
        });
    }

    // Initialize
    updateHeaderMeta();
    renderTranscript(data.lines);
    renderTopics(data.topics);
    if (data.topics.length > 0) {
        jumpToTopic(data.topics[0], 0);
    }
});
