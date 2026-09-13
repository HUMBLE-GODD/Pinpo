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

        // Highlight matching line range
        let firstLineEl = null;
        let curP = t.start_page;
        let curL = t.start_line;

        while (curP < t.end_page || (curP === t.end_page && curL <= t.end_line)) {
            const lineEl = document.getElementById(`line-${curP}-${curL}`);
            if (lineEl) {
                lineEl.classList.add("highlighted");
                if (!firstLineEl) {
                    firstLineEl = lineEl;
                    lineEl.classList.add("highlighted-first");
                }
                if (curP === t.end_page && curL === t.end_line) {
                    lineEl.classList.add("highlighted-last");
                }
            }
            curL++;
            if (curL > 25) {
                curP++;
                curL = 1;
            }
        }

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

    // Initialize
    updateHeaderMeta();
    renderTranscript(data.lines);
    renderTopics(data.topics);
});
