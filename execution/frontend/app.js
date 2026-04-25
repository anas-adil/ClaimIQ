// ClaimIQ v2 Frontend Logic

const API_BASE = (window.CLAIMIQ_API_BASE || `${window.location.origin}/api`).replace(/\/$/, "");
let currentView = "dashboard";
let currentLang = "en";
let charts = {};
let currentClaimContext = null;

// Initialization
document.addEventListener("DOMContentLoaded", () => {
    switchView("dashboard");
    loadDashboard();
    
    // Navigation Setup
    document.querySelectorAll(".nav-link").forEach(link => {
        link.addEventListener("click", (e) => {
            const view = e.currentTarget.dataset.view;
            if (view) switchView(view);
        });
    });

    // Global Search
    const searchInput = document.getElementById("globalSearch");
    if (searchInput) {
        searchInput.addEventListener("keyup", (e) => {
            if (e.key === "Enter") {
                switchView("claims");
                document.getElementById("filterClinic").value = e.target.value;
                loadClaims();
            }
        });
    }

    // Seed Demo Setup
    document.getElementById("btnSeedDemo").addEventListener("click", seedDemo);
});

// View Routing
function switchView(viewId) {
    document.querySelectorAll(".view").forEach(v => v.classList.remove("active"));
    document.querySelectorAll(".nav-link").forEach(l => l.classList.remove("active"));
    
    document.getElementById(`view${viewId.charAt(0).toUpperCase() + viewId.slice(1)}`).classList.add("active");
    
    const navLink = document.querySelector(`.nav-link[data-view="${viewId}"]`);
    if (navLink) navLink.classList.add("active");

    currentView = viewId;

    // Load data based on view
    if (viewId === "dashboard") loadDashboard();
    else if (viewId === "claims") loadClaims();
    else if (viewId === "denials") loadDenials();
    else if (viewId === "fraud") loadFraud();
    else if (viewId === "analytics") loadAnalytics();
    else if (viewId === "gpportal") loadGPPortal();
}

// Formatters
const fmtMYR = (val) => `RM ${Number(val).toFixed(2)}`;
const fmtDate = (str) => {
    if (!str) return "N/A";
    const d = new Date(str);
    return isNaN(d) ? str : d.toLocaleDateString();
};

// --- DASHBOARD ---
async function loadDashboard() {
    try {
        const [summary, claims] = await Promise.all([
            fetch(`${API_BASE}/analytics/summary`).then(r => r.json()),
            fetch(`${API_BASE}/claims/?limit=10`).then(r => r.json())
        ]);

        // KPIs
        const kpis = summary.kpis || {};
        document.getElementById("kpiCleanRate").textContent = `${kpis.clean_claim_rate || 0}%`;
        document.getElementById("kpiDenialRate").textContent = `${kpis.denial_rate || 0}%`;
        document.getElementById("kpiArDays").textContent = `${kpis.avg_ar_days || 0}`;
        document.getElementById("kpiAutoAdj").textContent = `${kpis.auto_adjudication_rate || 0}%`;

        // Stats
        document.getElementById("statTotal").textContent = summary.total_claims;
        document.getElementById("statApproved").textContent = (summary.by_status?.APPROVED || 0) + (summary.by_status?.APPEAL_APPROVED || 0);
        document.getElementById("statDenied").textContent = summary.by_status?.DENIED || 0;
        
        let fraudCount = 0;
        if(summary.fraud_by_risk_level) {
            fraudCount = (summary.fraud_by_risk_level.HIGH || 0) + (summary.fraud_by_risk_level.CRITICAL || 0);
        }
        document.getElementById("statFraud").textContent = fraudCount;
        document.getElementById("statAvg").textContent = summary.avg_claim_amount_myr.toFixed(2);
        document.getElementById("statApprovedAmt").textContent = (summary.total_approved_myr/1000).toFixed(1) + "k";

        renderRecentClaims(claims.claims);
        renderCharts(summary);
    } catch (e) {
        console.error("Dashboard error:", e);
    }
}

function renderRecentClaims(claims) {
    const wrap = document.getElementById("recentClaimsTable");
    if (!claims || claims.length === 0) {
        wrap.innerHTML = `<p class="empty-state">No claims found.</p>`;
        return;
    }

    let html = `<table><thead><tr>
        <th>ID</th><th>Date</th><th>Patient</th><th>Clinic</th><th>Diagnosis</th><th>Amount</th><th>Status</th>
    </tr></thead><tbody>`;

    claims.forEach(c => {
        html += `<tr class="tr-clickable" onclick="openClaim(${c.id})">
            <td class="td-mono">#${c.id}</td>
            <td>${fmtDate(c.visit_date)}</td>
            <td>${c.patient_name || 'Unknown'}</td>
            <td>${c.clinic_name || 'Unknown'}</td>
            <td>${c.diagnosis || 'Unknown'}</td>
            <td class="td-mono">${fmtMYR(c.total_amount_myr || 0)}</td>
            <td><span class="badge badge-${c.status}">${c.status}</span></td>
        </tr>`;
    });
    html += `</tbody></table>`;
    wrap.innerHTML = html;
}

// --- CHARTS ---
async function renderCharts(summary) {
    const statusCtx = document.getElementById('statusChart');
    if(charts.status) charts.status.destroy();
    
    const statuses = summary.by_status || {};
    charts.status = new Chart(statusCtx, {
        type: 'doughnut',
        data: {
            labels: Object.keys(statuses),
            datasets: [{
                data: Object.values(statuses),
                backgroundColor: ['#10B981', '#EF4444', '#F59E0B', '#3B82F6', '#8B5CF6'],
                borderWidth: 0
            }]
        },
        options: { plugins: { legend: { position: 'right', labels: {color: '#94A3B8'} } }, cutout: '70%' }
    });

    const denials = await fetch(`${API_BASE}/analytics/denials`).then(r => r.json());
    const denialCtx = document.getElementById('denialChart');
    if(charts.denial) charts.denial.destroy();
    
    if (denials.breakdown && denials.breakdown.length > 0) {
        charts.denial = new Chart(denialCtx, {
            type: 'bar',
            data: {
                labels: denials.breakdown.map(d => d.denial_reason_code || 'Unknown'),
                datasets: [{
                    label: 'Count',
                    data: denials.breakdown.map(d => d.count),
                    backgroundColor: '#EF4444'
                }]
            },
            options: {
                plugins: { legend: { display: false } },
                scales: { 
                    y: { beginAtZero: true, grid: {color: 'rgba(255,255,255,0.05)'}, ticks: {color: '#94A3B8'} },
                    x: { grid: {display: false}, ticks: {color: '#94A3B8'} }
                }
            }
        });
    }
}

// --- WEEKLY REPORT ---
async function loadWeeklyReport() {
    const el = document.getElementById("weeklyReportContent");
    el.innerHTML = `<p class="empty-state">GLM is analysing data and drafting report...</p>`;
    try {
        const report = await fetch(`${API_BASE}/analytics/weekly-report`).then(r => r.json());
        let html = `<div class="report-content">`;
        html += `<p style="font-size:1.1rem;margin-bottom:12px;">${report.executive_summary || 'Report generated.'}</p>`;
        
        if (report.key_highlights) {
            html += `<h3>Key Highlights</h3><ul>`;
            report.key_highlights.forEach(h => {
                html += `<li><strong>${h.metric}:</strong> ${h.value} (${h.insight})</li>`;
            });
            html += `</ul>`;
        }
        
        if (report.fraud_alerts && report.fraud_alerts.length > 0) {
            html += `<h3>Fraud Alerts</h3><ul>`;
            report.fraud_alerts.forEach(a => html += `<li><span style="color:var(--accent-red)">⚠️</span> ${a}</li>`);
            html += `</ul>`;
        }
        
        html += `</div>`;
        el.innerHTML = html;
    } catch (e) {
        el.innerHTML = `<p class="empty-state" style="color:var(--accent-red)">Failed to generate report.</p>`;
    }
}

// --- CLAIMS QUEUE ---
async function loadClaims() {
    const clinic = document.getElementById("filterClinic").value;
    const status = document.getElementById("claimStatusFilter").value;
    let url = `${API_BASE}/claims/?limit=200`;
    if (clinic) url += `&clinic=${encodeURIComponent(clinic)}`;
    if (status) url += `&status=${status}`;

    try {
        const res = await fetch(url).then(r => r.json());
        const wrap = document.getElementById("claimsTable");
        if (!res.claims || res.claims.length === 0) {
            wrap.innerHTML = `<p class="empty-state">No claims match filters.</p>`;
            return;
        }

        let html = `<table><thead><tr>
            <th>ID</th><th>Submitted</th><th>Clinic</th><th>Patient</th><th>Diagnosis</th><th>Amount</th><th>Status</th>
        </tr></thead><tbody>`;

        res.claims.forEach(c => {
            html += `<tr class="tr-clickable" onclick="openClaim(${c.id})">
                <td class="td-mono">#${c.id}</td>
                <td>${fmtDate(c.created_at)}</td>
                <td>${c.clinic_name || 'N/A'}</td>
                <td>${c.patient_name || 'N/A'}<br><span style="font-size:0.75rem;color:var(--text-secondary)">${c.patient_ic || ''}</span></td>
                <td>${c.diagnosis || 'N/A'}<br><span style="font-size:0.75rem;color:var(--text-secondary)">${c.icd10_code || ''}</span></td>
                <td class="td-mono">${fmtMYR(c.total_amount_myr || 0)}</td>
                <td>
                    <span class="badge badge-${c.status || 'UNKNOWN'}">${c.status || 'UNKNOWN'}</span>
                    <div class="lifecycle-bar">
                        <div class="lifecycle-fill lc-${(c.status || 'unknown').toLowerCase()}"></div>
                    </div>
                </td>
            </tr>`;
        });
        html += `</tbody></table>`;
        wrap.innerHTML = html;
    } catch (e) {
        console.error("Claims error:", e);
    }
}

// --- DENIALS VIEW ---
async function loadDenials() {
    try {
        const [denials, claims] = await Promise.all([
            fetch(`${API_BASE}/analytics/denials`).then(r => r.json()),
            fetch(`${API_BASE}/claims/?status=DENIED&limit=50`).then(r => r.json())
        ]);

        // Codes
        let codesHtml = ``;
        if (denials.breakdown && denials.breakdown.length > 0) {
            denials.breakdown.forEach(d => {
                codesHtml += `<div class="detail-card" style="margin-bottom:8px;">
                    <div class="detail-row" style="border:none;margin:0;padding:0;">
                        <div>
                            <span style="font-family:var(--font-mono);color:var(--accent-red);font-weight:bold;">CARC ${d.denial_reason_code}</span>
                            <div style="font-size:0.85rem;color:var(--text-secondary);">${d.denial_reason_description}</div>
                        </div>
                        <div style="font-size:1.5rem;font-weight:bold;font-family:var(--font-mono);">${d.count}</div>
                    </div>
                </div>`;
            });
        } else {
            codesHtml = `<p class="empty-state">No denials recorded.</p>`;
        }
        document.getElementById("denialCodesList").innerHTML = codesHtml;

        // List
        let listHtml = ``;
        if (claims.claims && claims.claims.length > 0) {
            claims.claims.forEach(c => {
                listHtml += `<div class="detail-card" style="margin-bottom:8px;cursor:pointer;" onclick="openClaim(${c.id})">
                    <div style="display:flex;justify-content:space-between;margin-bottom:4px;">
                        <span style="font-weight:bold;">Claim #${c.id} — ${c.clinic_name}</span>
                        <span class="td-mono">${fmtMYR(c.total_amount_myr)}</span>
                    </div>
                    <div style="font-size:0.85rem;color:var(--text-secondary);">${c.patient_name} • ${c.diagnosis}</div>
                    <div style="margin-top:8px;"><button class="btn btn-sm btn-ghost" onclick="event.stopPropagation();showAppealModal(${c.id})">Appeal with GLM</button></div>
                </div>`;
            });
        } else {
            listHtml = `<p class="empty-state">No denied claims found.</p>`;
        }
        document.getElementById("deniedClaimsList").innerHTML = listHtml;

    } catch (e) {
        console.error("Denials error:", e);
    }
}

// --- FRAUD VIEW ---
async function loadFraud() {
    try {
        const hm = await fetch(`${API_BASE}/analytics/fraud-heatmap`).then(r => r.json());
        const data = hm.heatmap_data || [];
        
        let counts = { LOW: 0, MEDIUM: 0, HIGH: 0, CRITICAL: 0 };
        data.forEach(d => counts[d.risk_level]++);
        const total = data.length || 1;

        // Bars
        let barsHtml = ``;
        ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL'].forEach(level => {
            const pct = (counts[level] / total) * 100;
            const color = level === 'LOW' ? 'var(--accent-green)' : (level === 'MEDIUM' ? 'var(--accent-yellow)' : 'var(--accent-red)');
            barsHtml += `<div class="risk-bar-row">
                <div class="risk-bar-label">${level}</div>
                <div class="risk-bar-track"><div class="risk-bar-fill" style="width:${pct}%;background:${color};"></div></div>
                <div class="risk-bar-val">${counts[level]}</div>
            </div>`;
        });
        document.getElementById("fraudRiskBars").innerHTML = barsHtml;

        // Flagged List
        const flagged = data.filter(d => d.risk_level === 'HIGH' || d.risk_level === 'CRITICAL');
        let listHtml = ``;
        if (flagged.length > 0) {
            flagged.forEach(f => {
                listHtml += `<div class="detail-card" style="margin-bottom:8px;cursor:pointer;" onclick="openClaim(${f.claim_id})">
                    <div style="display:flex;justify-content:space-between;margin-bottom:4px;">
                        <span style="font-weight:bold;">${f.clinic_name} — ${f.diagnosis}</span>
                        <span class="badge badge-DENIED">${f.risk_level}</span>
                    </div>
                    <div style="font-size:0.85rem;color:var(--text-secondary);">Risk Score: ${f.risk_score.toFixed(2)} | Amount: ${fmtMYR(f.total_amount_myr)}</div>
                </div>`;
            });
        } else {
            listHtml = `<p class="empty-state">No high risk claims found.</p>`;
        }
        document.getElementById("flaggedClaims").innerHTML = listHtml;
    } catch (e) {
        console.error("Fraud error:", e);
    }
}

// --- ANALYTICS VIEW ---
async function loadAnalytics() {
    try {
        const data = await fetch(`${API_BASE}/analytics/clinics`).then(r => r.json());
        const wrap = document.getElementById("clinicTable");
        if (!data.clinics || data.clinics.length === 0) {
            wrap.innerHTML = `<p class="empty-state">No data.</p>`;
            return;
        }

        let html = `<table><thead><tr>
            <th>Clinic</th><th>Total Claims</th><th>Denial Rate</th><th>Fraud Flags</th><th>Avg Amount</th><th>Avg Approved</th>
        </tr></thead><tbody>`;

        data.clinics.forEach(c => {
            html += `<tr>
                <td style="font-weight:600;">${c.clinic_name}</td>
                <td class="td-mono">${c.total_claims}</td>
                <td class="td-mono" style="color:${c.denial_rate > 10 ? 'var(--accent-red)' : 'var(--text-secondary)'}">${c.denial_rate}%</td>
                <td class="td-mono">${c.fraud_flagged}</td>
                <td class="td-mono">${fmtMYR(c.avg_amount)}</td>
                <td class="td-mono" style="color:var(--accent-green)">${fmtMYR(c.avg_approved || 0)}</td>
            </tr>`;
        });
        html += `</tbody></table>`;
        wrap.innerHTML = html;
    } catch (e) {
        console.error("Analytics error:", e);
    }
}

// --- GP PORTAL ---
function setLang(lang) {
    currentLang = lang;
    document.getElementById("langEN").classList.toggle("active", lang === "en");
    document.getElementById("langBM").classList.toggle("active", lang === "bm");
    
    // Update data attributes
    document.querySelectorAll('[data-en]').forEach(el => {
        el.textContent = el.getAttribute(`data-${lang}`);
    });
    
    loadGPPortal(); // Reload data with language
}

async function loadGPPortal() {
    try {
        const claims = await fetch(`${API_BASE}/claims/?limit=20`).then(r => r.json());
        const data = claims.claims || [];
        
        let total = data.length;
        let approved = data.filter(c => c.status === 'APPROVED' || c.status === 'APPEAL_APPROVED').length;
        let denied = data.filter(c => c.status === 'DENIED').length;
        let pending = data.filter(c => c.status === 'PENDING' || c.status === 'PROCESSING').length;

        // Stats
        document.getElementById("gpSummaryStats").innerHTML = `
            <div class="kpi-grid" style="grid-template-columns: 1fr 1fr; gap: 16px;">
                <div class="kpi-card kpi-blue"><div class="kpi-val">${total}</div><div class="kpi-label">${currentLang === 'en' ? 'Total Submitted' : 'Jumlah Dihantar'}</div></div>
                <div class="kpi-card kpi-green"><div class="kpi-val">${approved}</div><div class="kpi-label">${currentLang === 'en' ? 'Approved' : 'Diluluskan'}</div></div>
                <div class="kpi-card kpi-red"><div class="kpi-val">${denied}</div><div class="kpi-label">${currentLang === 'en' ? 'Denied' : 'Ditolak'}</div></div>
                <div class="kpi-card kpi-yellow"><div class="kpi-val">${pending}</div><div class="kpi-label">${currentLang === 'en' ? 'Pending' : 'Dalam Proses'}</div></div>
            </div>
        `;

        // Table
        let html = `<table><thead><tr>
            <th>ID</th><th>${currentLang==='en'?'Patient':'Pesakit'}</th><th>${currentLang==='en'?'Date':'Tarikh'}</th><th>Amount (RM)</th><th>Status</th><th>Action</th>
        </tr></thead><tbody>`;

        data.forEach(c => {
            html += `<tr class="tr-clickable" onclick="openClaim(${c.id})">
                <td class="td-mono">#${c.id}</td>
                <td>${c.patient_name || 'N/A'}</td>
                <td>${fmtDate(c.visit_date)}</td>
                <td class="td-mono">${(c.total_amount_myr||0).toFixed(2)}</td>
                <td><span class="badge badge-${c.status}">${c.status}</span></td>
                <td>${c.status === 'DENIED' ? `<button class="btn btn-sm btn-ghost" onclick="event.stopPropagation();showAppealModal(${c.id})">${currentLang==='en'?'Appeal':'Rayuan'}</button>` : ''}</td>
            </tr>`;
        });
        html += `</tbody></table>`;
        document.getElementById("gpClaimsTable").innerHTML = html;
    } catch (e) {
        console.error("GP error:", e);
    }
}

// File Handlers
function handleFileSelect(inputId, displayId) {
    const input = document.getElementById(inputId);
    const displayElement = document.getElementById(displayId);
    if (input.files && input.files[0]) {
        const file = input.files[0];
        displayElement.innerHTML = `<div>Attached: <b>${file.name}</b></div>`;
        
        if (file.type.startsWith('image/')) {
            const reader = new FileReader();
            reader.onload = function(e) {
                displayElement.innerHTML += `<img src="${e.target.result}" style="max-height: 120px; border-radius: 4px; margin-top: 10px; border: 1px solid rgba(255,255,255,0.2);">`;
            }
            reader.readAsDataURL(file);
        }
    }
}

// --- CLAIM SUBMISSION PIPELINE ---
async function submitClaim() {
    const notes = document.getElementById("claimTextInput").value;
    const fileBill = document.getElementById("fileBill").files[0];
    const fileEvidence = document.getElementById("fileEvidence").files[0];
    
    if (!notes.trim() && !fileBill && !fileEvidence) return alert("Please provide clinical notes or attach evidence.");

    const btnSubmit = document.getElementById("btnSubmitClaim");
    btnSubmit.disabled = true;
    
    document.getElementById("processingPanel").style.display = "block";
    document.getElementById("processingResult").innerHTML = "";

    // Reset pipeline UI
    document.querySelectorAll(".pipeline-step").forEach(el => {
        el.classList.remove("active", "done");
    });

    const activateStep = (step) => {
        document.querySelectorAll(".pipeline-step").forEach(el => el.classList.remove("active"));
        const el = document.querySelector(`.pipeline-step[data-step="${step}"]`);
        if (el) el.classList.add("active");
    };
    const finishStep = (step) => {
        const el = document.querySelector(`.pipeline-step[data-step="${step}"]`);
        if (el) { el.classList.remove("active"); el.classList.add("done"); }
    };

    try {
        let evidenceBase64 = null;
        if (fileEvidence && fileEvidence.type.startsWith('image/')) {
            evidenceBase64 = await new Promise((resolve) => {
                const reader = new FileReader();
                reader.onload = e => resolve(e.target.result);
                reader.readAsDataURL(fileEvidence);
            });
        }

        let invoiceBase64 = null;
        if (fileBill && fileBill.type.startsWith('image/')) {
            invoiceBase64 = await new Promise((resolve) => {
                const reader = new FileReader();
                reader.onload = e => resolve(e.target.result);
                reader.readAsDataURL(fileBill);
            });
        }

        if (fileBill || fileEvidence) {
            btnSubmit.innerHTML = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line></svg> Parsing Documents...`;
            await new Promise(r => setTimeout(r, 1200));
        }
        btnSubmit.innerHTML = "Initializing Claim...";

        const getField = (label, fallback = "") => {
            const m = notes.match(new RegExp(`(?:^|\\n)\\s*${label}\\s*:\\s*(.+)`, "i"));
            return (m && m[1] ? m[1].trim() : fallback).split("\n")[0].trim();
        };
        const patientName = getField("Name");
        const patientIc = getField("IC");
        const clinicName = getField("Clinic");
        const visitDate = getField("Date");
        const totalText = getField("Total");
        const amountMatch = totalText.match(/(\d+(\.\d+)?)/);
        const totalAmount = amountMatch ? Number(amountMatch[1]) : null;
        if (!patientName || !patientIc || !clinicName || !visitDate || totalAmount === null) {
            throw new Error("Missing required fields in notes. Include lines: Name:, IC:, Clinic:, Date:(YYYY-MM-DD), Total:(RM).");
        }

        const payload = {
            raw_text: notes,
            bill_attached: !!fileBill,
            evidence_attached: !!fileEvidence,
            evidence_base64: evidenceBase64,
            invoice_base64: invoiceBase64,
            patient_name: patientName,
            patient_ic: patientIc,
            clinic_name: clinicName,
            visit_date: visitDate,
            total_amount_myr: totalAmount
        };

        // Step 0: Intake
        const initRes = await fetch(`${API_BASE}/claims/submit`, {
            method: "POST", headers: {"Content-Type": "application/json"},
            body: JSON.stringify(payload)
        }).then(r => r.json());
        const claimId = initRes.claim_id;

        // Steps sequence simulation for UI (actual processing happens on backend)
        const steps = ["scrub", "eligibility", "extract", "validate", "code", "adjudicate", "fraud", "advisory"];
        
        // Start backend process
        const processPromise = fetch(`${API_BASE}/claims/process/${claimId}`, {method: "POST"}).then(r => r.json());

        // Animate UI while waiting
        for(let i=0; i<steps.length; i++) {
            activateStep(steps[i]);
            await new Promise(r => setTimeout(r, 600 + Math.random()*400)); // Fake wait for UI
            finishStep(steps[i]);
        }

        const result = await processPromise;
        
        document.getElementById("processingResult").innerHTML = `
            <div style="margin-top:20px; padding:20px; background:rgba(255,255,255,0.05); border-radius:12px; text-align:center;">
                <h3 style="margin-bottom:8px;">Claim #${claimId} Processed Successfully</h3>
                <span class="badge badge-${result.final_status}" style="font-size:1.1rem; padding:8px 16px;">${result.final_status}</span>
                <p style="margin-top:16px;"><button class="btn btn-primary" onclick="openClaim(${claimId})">View Claim Details</button></p>
            </div>
        `;
    } catch (e) {
        document.getElementById("processingResult").innerHTML = `<p style="color:var(--accent-red)">Error: ${e.message}</p>`;
    } finally {
        document.getElementById("btnSubmitClaim").disabled = false;
    }
}


// --- CLAIM DETAIL & MODALS ---
async function openClaim(id) {
    document.getElementById("claimModal").classList.add("active");
    const body = document.getElementById("modalBody");
    body.innerHTML = `<p class="empty-state">Loading claim data...</p>`;
    document.getElementById("chatMessages").innerHTML = `<div class="chat-msg chat-msg-system">Hi! Ask me anything about this claim.</div>`;
    
    try {
        const claim = await fetch(`${API_BASE}/claims/${id}`).then(r => r.json());
        currentClaimContext = claim;
        
        let html = `
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <div>
                    <h2 style="margin:0;color:#fff;">Claim #${claim.id}</h2>
                    <div style="margin-top:8px;">
                        <span class="badge badge-${claim.status || 'UNKNOWN'}">${claim.status || 'UNKNOWN'}</span>
                        <span style="color:var(--text-secondary);font-size:0.85rem;margin-left:12px;">Filed: ${fmtDate(claim.filing_date)}</span>
                    </div>
                </div>
                ${(claim.status === 'DENIED' || claim.status === 'REFERRED' || claim.status === 'PENDING_APPROVAL') ? `<button class="btn btn-primary" onclick="showAppealModal(${claim.id})">Appeal</button>` : ''}
            </div>

            <!-- Lifecycle -->
            <div style="margin-top:24px;">
                <div style="font-size:0.8rem;color:var(--text-secondary);margin-bottom:4px;text-transform:uppercase;">Lifecycle Progress</div>
                <div class="lifecycle-bar" style="height:8px;">
                    <div class="lifecycle-fill lc-${(claim.status || 'unknown').toLowerCase()}"></div>
                </div>
            </div>

            <div class="claim-detail-grid">
                <!-- Left Col -->
                <div>
                    <div class="detail-card" style="margin-bottom:24px;">
                        <h3 style="margin-bottom:16px;font-size:0.9rem;text-transform:uppercase;color:var(--text-secondary);">Patient & Visit</h3>
                        <div class="detail-row"><span class="detail-label">Patient</span><span class="detail-value">${claim.patient_name || 'N/A'}<br><span style="font-size:0.8rem;color:var(--text-secondary)">${claim.patient_ic || ''}</span></span></div>
                        <div class="detail-row"><span class="detail-label">Clinic</span><span class="detail-value">${claim.clinic_name || 'N/A'}</span></div>
                        <div class="detail-row"><span class="detail-label">Diagnosis</span><span class="detail-value">${claim.diagnosis || 'N/A'}<br><span style="font-size:0.8rem;color:var(--text-secondary)">${claim.icd10_code || ''}</span></span></div>
                        <div class="detail-row"><span class="detail-label">Total Amount</span><span class="detail-value td-mono">${fmtMYR(claim.total_amount_myr)}</span></div>
                    </div>

                    ${claim.eob ? `
                    <div class="eob-card">
                        <div class="eob-header">
                            <h3 style="margin:0;font-size:0.9rem;text-transform:uppercase;color:var(--accent-blue);">Explanation of Benefits (EOB)</h3>
                            <span class="badge badge-INTAKE">Generated</span>
                        </div>
                        <div class="eob-amount-row"><span>Billed Amount</span><span>${fmtMYR(claim.eob.billed_amount_myr)}</span></div>
                        <div class="eob-amount-row"><span>Covered by Plan</span><span>${fmtMYR(claim.eob.covered_amount_myr)}</span></div>
                        <div class="eob-amount-row total"><span>Patient Responsibility (Copay/Limits)</span><span>${fmtMYR(claim.eob.patient_responsibility_myr)}</span></div>
                        ${claim.eob.denial_code ? `<div class="eob-denial"><strong>CARC ${claim.eob.denial_code}:</strong> ${claim.eob.denial_description}</div>` : ''}
                    </div>` : ''}

                    <div class="detail-card" style="margin-top:24px;">
                        <h3 style="margin-bottom:16px;font-size:0.9rem;text-transform:uppercase;color:var(--text-secondary);">Audit Timeline</h3>
                        <div class="audit-timeline">
                            ${(claim.audit_trail || []).map(a => `
                                <div class="audit-item">
                                    <div class="audit-time">${new Date(a.created_at).toLocaleString()}</div>
                                    <div class="audit-action">${a.action.replace(/_/g, ' ')}</div>
                                    ${a.to_status ? `<div style="font-size:0.8rem;color:var(--text-secondary)">Status ➔ ${a.to_status}</div>` : ''}
                                </div>
                            `).join('')}
                        </div>
                    </div>
                </div>

                <!-- Right Col -->
                <div>
                    ${claim.decision ? `
                    <div class="detail-card" style="margin-bottom:24px;">
                        <h3 style="margin-bottom:16px;font-size:0.9rem;text-transform:uppercase;color:var(--text-secondary);">Adjudication Decision</h3>
                        <div style="margin-bottom:16px;">
                            <span class="badge badge-${claim.decision.decision}">${claim.decision.decision}</span>
                            <span style="float:right;font-family:var(--font-mono);font-size:0.85rem;color:var(--text-secondary);">Conf: ${(claim.decision.confidence*100).toFixed(0)}%</span>
                        </div>
                        <p style="font-size:0.9rem;line-height:1.5;background:rgba(0,0,0,0.2);padding:12px;border-radius:var(--radius-sm);">${claim.decision.reasoning}</p>
                    </div>` : ''}

                    ${claim.fraud ? `
                    <div class="detail-card" style="margin-bottom:24px;">
                        <h3 style="margin-bottom:16px;font-size:0.9rem;text-transform:uppercase;color:var(--text-secondary);">Fraud Analysis</h3>
                        <div style="display:flex;align-items:center;gap:16px;margin-bottom:16px;">
                            <div class="fraud-gauge gauge-${claim.fraud.risk_level}">${(claim.fraud.risk_score*100).toFixed(0)}%</div>
                            <div>
                                <div style="font-weight:bold;">${claim.fraud.risk_level} Risk</div>
                                <div style="font-size:0.85rem;color:var(--text-secondary);">Recommendation: ${claim.fraud.recommendation}</div>
                            </div>
                        </div>
                    </div>` : ''}

                    ${claim.advisory ? `
                    <div class="detail-card">
                        <h3 style="margin-bottom:16px;font-size:0.9rem;text-transform:uppercase;color:var(--accent-purple);">GP Advisory</h3>
                        <p style="font-size:0.9rem;line-height:1.5;margin-bottom:12px;">${claim.advisory.summary}</p>
                        ${currentLang === 'bm' && claim.advisory.summary_bm ? `<p style="font-size:0.9rem;line-height:1.5;margin-bottom:12px;color:var(--text-secondary);font-style:italic;">${claim.advisory.summary_bm}</p>` : ''}
                    </div>` : ''}
                </div>
            </div>
        `;
        body.innerHTML = html;

        // Update suggested chat questions
        updateChatSuggestions();

    } catch (e) {
        body.innerHTML = `<p class="empty-state" style="color:var(--accent-red)">Error loading claim: ${e.message}</p>`;
    }
}

function closeModal() { document.getElementById("claimModal").classList.remove("active"); currentClaimContext = null; }

// --- CHAT ---
function updateChatSuggestions(questions) {
    const defaultQs = ["Why was this decision made?", "What is the fraud risk based on?", "How can I avoid denials for this?"];
    const qs = questions || defaultQs;
    const wrap = document.getElementById("chatSuggested");
    wrap.innerHTML = qs.map(q => `<button class="chat-sugg-btn" onclick="document.getElementById('chatInput').value='${q}';sendChatMessage();">${q}</button>`).join('');
}

async function sendChatMessage() {
    const input = document.getElementById("chatInput");
    const text = input.value.trim();
    if (!text || !currentClaimContext) return;
    
    const messages = document.getElementById("chatMessages");
    messages.innerHTML += `<div class="chat-msg chat-msg-user">${text}</div>`;
    input.value = "";
    messages.scrollTop = messages.scrollHeight;
    
    const loadingId = "msg-" + Date.now();
    messages.innerHTML += `<div class="chat-msg chat-msg-system" id="${loadingId}">Thinking...</div>`;
    messages.scrollTop = messages.scrollHeight;

    try {
        const response = await fetch(`${API_BASE}/claims/${currentClaimContext.id}/chat`, {
            method: "POST", headers: {"Content-Type": "application/json"},
            body: JSON.stringify({ question: text })
        });
        const res = await response.json();
        
        if (!response.ok) {
            throw new Error(res.detail || "Error communicating with GLM.");
        }
        
        document.getElementById(loadingId).innerText = currentLang === 'bm' && res.answer_bm ? res.answer_bm : res.answer;
        if (res.follow_up_questions) updateChatSuggestions(res.follow_up_questions);
    } catch (e) {
        document.getElementById(loadingId).innerText = e.message || "Error communicating with GLM.";
    }
}

// --- APPEAL ---
function showAppealModal(claimId) {
    document.getElementById("appealModal").classList.add("active");
    document.getElementById("appealModal").dataset.claimId = claimId;
    document.getElementById("appealReason").value = "";
    document.getElementById("appealResult").style.display = "none";
}
function closeAppealModal() { document.getElementById("appealModal").classList.remove("active"); }

async function submitAppeal() {
    const claimId = document.getElementById("appealModal").dataset.claimId;
    const reason = document.getElementById("appealReason").value;
    if (!reason.trim()) return alert("Please provide a reason.");
    
    const btn = document.querySelector("#appealModal .btn-primary");
    btn.disabled = true; btn.innerText = "GLM is drafting rebuttal...";
    
    try {
        const res = await fetch(`${API_BASE}/claims/${claimId}/appeal`, {
            method: "POST", headers: {"Content-Type": "application/json"},
            body: JSON.stringify({ appeal_reason: reason })
        }).then(r => r.json());
        
        const resDiv = document.getElementById("appealResult");
        resDiv.style.display = "block";
        resDiv.innerHTML = `
            <div style="background:rgba(16,185,129,0.1);border:1px solid var(--accent-green);padding:16px;border-radius:8px;">
                <h3 style="color:var(--accent-green);margin-bottom:8px;">Appeal Submitted (#${res.appeal_id})</h3>
                <p style="font-size:0.85rem;margin-bottom:12px;">GLM drafted formal rebuttal:</p>
                <div style="background:rgba(0,0,0,0.3);padding:12px;border-radius:4px;font-size:0.85rem;white-space:pre-wrap;max-height:200px;overflow-y:auto;">${currentLang === 'bm' && res.rebuttal.rebuttal_body_bm ? res.rebuttal.rebuttal_body_bm : res.rebuttal.rebuttal_body}</div>
            </div>
        `;
        if(currentView === 'claims') loadClaims();
        if(currentView === 'denials') loadDenials();
        if(currentView === 'gpportal') loadGPPortal();
    } catch (e) {
        alert("Failed to submit appeal.");
    } finally {
        btn.disabled = false; btn.innerText = "Draft Appeal with GLM";
    }
}

// --- UTILS ---
async function seedDemo() {
    const btn = document.getElementById("btnSeedDemo");
    btn.disabled = true; btn.innerText = "Seeding...";
    try {
        await fetch(`${API_BASE}/demo/seed`, { method: "POST" });
        alert("Demo data seeded successfully.");
        loadDashboard();
    } catch (e) {
        alert("Seeding failed.");
    } finally {
        btn.disabled = false; btn.innerText = "Seed Demo";
    }
}

function toggleNotif() {
    const d = document.getElementById("notifDrawer");
    d.classList.toggle("open");
}
document.getElementById("notifBtn").addEventListener("click", toggleNotif);
