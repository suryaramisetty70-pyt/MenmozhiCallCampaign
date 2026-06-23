// ===== LIVE CLOCK =====
(function(){
  const el=document.getElementById('clock');
  const tick=()=>{
    const now=new Date();
    el.textContent=now.toLocaleTimeString('en-IN',{hour12:true,hour:'2-digit',minute:'2-digit',second:'2-digit'});
  };
  tick();setInterval(tick,1000);
})();

// ===== TABS =====
document.querySelectorAll('.tab-btn').forEach(btn=>{
  btn.addEventListener('click',()=>{
    document.querySelectorAll('.tab-btn').forEach(b=>b.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(p=>p.classList.remove('active'));
    btn.classList.add('active');
    document.getElementById('panel-'+btn.dataset.tab).classList.add('active');
  });
});

// ===== SEARCH / FILTER =====
function filterTable(tableId,query){
  const rows=document.querySelectorAll('#'+tableId+' tbody tr');
  const q=query.toLowerCase();
  rows.forEach(row=>{
    if(row.querySelector('.empty')){row.style.display='';return;}
    const text=row.textContent.toLowerCase();
    row.style.display=text.includes(q)?'':'none';
  });
}

// ===== CONFIRMATION MODAL =====
function confirmAction(title,message,url, isAjax=false){
  document.getElementById('modal-title').textContent=title;
  document.getElementById('modal-message').textContent=message;
  let confirmBtn = document.getElementById('modal-confirm');
  
  if (isAjax) {
      confirmBtn.removeAttribute('href');
      confirmBtn.onclick = function(e) {
          e.preventDefault();
          closeModal();
          launchCampaign();
      };
  } else {
      confirmBtn.href=url;
      confirmBtn.onclick = null;
  }
  document.getElementById('confirmModal').classList.add('show');
}
function closeModal(){
  document.getElementById('confirmModal').classList.remove('show');
}
document.getElementById('confirmModal').addEventListener('click',function(e){
  if(e.target===this) closeModal();
});

// ===== UNIVERSAL SEARCH =====
function universalSearch(query) {
    const q = query.toLowerCase();
    const tables = ['contacts-table', 'available-table', 'not-available-table', 'no-response-table', 'logs-table'];
    tables.forEach(tableId => {
        const rows = document.querySelectorAll('#' + tableId + ' tbody tr');
        rows.forEach(row => {
            if (row.querySelector('.empty')) { row.style.display = ''; return; }
            const text = row.textContent.toLowerCase();
            row.style.display = text.includes(q) ? '' : 'none';
        });
    });
}

// ===== AJAX CALLS =====
async function callContact(id, name) {
    showToast("Initiating call to " + name + "...", "info");
    try {
        let res = await fetch("/call/" + id);
        let data = await res.json();
        if(data.status === "success") {
            showToast("Call connected to " + name, "success");
        } else {
            showToast("Call failed: " + data.message, "error");
        }
    } catch(e) {
        showToast("Network error initiating call.", "error");
    }
}

async function launchCampaign() {
    showToast("Starting mass campaign (10s delay per call)...", "info");
    try {
        let res = await fetch("/call-all");
        let data = await res.json();
        if(data.status === "success") {
            showToast("Campaign running in background!", "success");
        } else {
            showToast("Campaign failed to start.", "error");
        }
    } catch(e) {
        showToast("Network error starting campaign.", "error");
    }
}

// ===== AUTO-POLLING LOGS =====
setInterval(async () => {
    const token = localStorage.getItem('access_token');
    if (!token) return;
    try {
        const response = await fetch('/api/logs', {
            headers: { 'Authorization': 'Bearer ' + token }
        });
        if (response.ok) {
            const data = await response.json();
            updateTables(data.logs);
        } else if (response.status === 401) {
            logout();
        }
    } catch (err) {
        // silently fail on polling error
    }
}, 3000);

function updateTables(logs) {
    let availHtml = ''; let notAvailHtml = ''; let noRespHtml = ''; let allLogsHtml = '';
    let availCount = 0; let notAvailCount = 0; let noRespCount = 0;

    logs.forEach(row => {
        let statusHtml = '';
        if (row.status === 'AVAILABLE') {
            statusHtml = '<span class="chip ok">AVAILABLE</span>';
            availHtml += `<tr><td class="name-cell">${row.name}</td><td class="phone-cell">${row.phone}</td><td>${statusHtml}</td><td class="time-cell">${row.call_time}</td></tr>`;
            availCount++;
        } else if (row.status === 'NOT AVAILABLE') {
            statusHtml = '<span class="chip error">NOT AVAILABLE</span>';
            notAvailHtml += `<tr><td class="name-cell">${row.name}</td><td class="phone-cell">${row.phone}</td><td>${statusHtml}</td><td class="time-cell">${row.call_time}</td></tr>`;
            notAvailCount++;
        } else {
            statusHtml = '<span class="chip pending">NO RESPONSE</span>';
            noRespHtml += `<tr><td class="name-cell">${row.name}</td><td class="phone-cell">${row.phone}</td><td>${statusHtml}</td><td class="time-cell">${row.call_time}</td></tr>`;
            noRespCount++;
        }
        allLogsHtml += `<tr><td>${row.id}</td><td class="name-cell">${row.name}</td><td class="phone-cell">${row.phone}</td><td>${statusHtml}</td><td class="time-cell">${row.call_time}</td></tr>`;
    });

    // Update table bodies
    document.querySelector('#available-table tbody').innerHTML = availHtml || '<tr><td colspan="4" class="empty">// No data</td></tr>';
    document.querySelector('#not-available-table tbody').innerHTML = notAvailHtml || '<tr><td colspan="4" class="empty">// No data</td></tr>';
    document.querySelector('#no-response-table tbody').innerHTML = noRespHtml || '<tr><td colspan="4" class="empty">// No data</td></tr>';
    document.querySelector('#logs-table tbody').innerHTML = allLogsHtml || '<tr><td colspan="5" class="empty">// No data</td></tr>';

    // Update counts
    document.querySelector('#panel-available .count').textContent = availCount;
    document.querySelector('#panel-not-available .count').textContent = notAvailCount;
    document.querySelector('#panel-no-response .count').textContent = noRespCount;
    document.querySelector('#panel-logs .count').textContent = logs.length + ' entries';

    // Update charts & stats
    document.getElementById('donut-total').textContent = logs.length;
    document.getElementById('legend-avail').textContent = availCount;
    document.getElementById('legend-notavail').textContent = notAvailCount;
    document.getElementById('legend-noresp').textContent = noRespCount;
    document.getElementById('ana-calls').textContent = logs.length;

    if (logs.length > 0) {
        document.getElementById('ana-rate').textContent = ((availCount / logs.length) * 100).toFixed(1) + '%';
        document.querySelector('.stat-row:nth-child(4) .stat-val').textContent = ((notAvailCount / logs.length) * 100).toFixed(1) + '%';
    }

    // Reapply universal search filter to newly rendered rows if there is a query
    const searchVal = document.getElementById('universal-search')?.value;
    if (searchVal) {
        universalSearch(searchVal);
    }
}

// ===== TOAST =====
function showToast(message,type='success'){
  const container=document.getElementById('toastContainer');
  const toast=document.createElement('div');
  toast.className='toast '+type;
  toast.innerHTML=(type==='success'?'âœ…':'âŒ')+' '+message;
  container.appendChild(toast);
  setTimeout(()=>toast.remove(),3500);
}

// ===== UPDATE ALL DASHBOARD STATS & DONUT =====
function updateDashboardStats(d) {
  // Update main card numbers
  document.getElementById('stat-contacts').textContent = d.total_contacts;
  document.getElementById('stat-calls').textContent = d.total_calls;
  document.getElementById('stat-available').textContent = d.available;
  document.getElementById('stat-not-available').textContent = d.not_available;
  document.getElementById('stat-no-response').textContent = d.no_response;

  // Update card progress bar widths
  document.querySelector('.card.c-violet .card-bar span').style.width = 
    `${Math.min(100, Math.round(d.total_calls / (d.total_contacts || 1) * 100))}%`;
  document.querySelector('.card.c-green .card-bar span').style.width = 
    `${Math.min(100, Math.round(d.available / (d.total_calls || 1) * 100))}%`;
  document.querySelector('.card.c-red .card-bar span').style.width = 
    `${Math.min(100, Math.round(d.not_available / (d.total_calls || 1) * 100))}%`;
  document.querySelector('.card.c-amber .card-bar span').style.width = 
    `${Math.min(100, Math.round(d.no_response / (d.total_calls || 1) * 100))}%`;

  // Update Analytics Tab Stats
  document.getElementById('ana-contacts').textContent = d.total_contacts;
  document.getElementById('ana-calls').textContent = d.total_calls;
  document.getElementById('ana-rate').textContent = `${d.success_rate}%`;
  
  const rejectionRate = d.total_calls > 0 ? Math.round((d.not_available / d.total_calls) * 1000) / 10 : 0;
  const pendingRate = d.total_calls > 0 ? Math.round((d.no_response / d.total_calls) * 1000) / 10 : 0;
  
  const rejectionEl = document.querySelector('.stat-row span[style*="color:var(--red)"]');
  if (rejectionEl) rejectionEl.textContent = `${rejectionRate}%`;
  
  const pendingEl = document.querySelector('.stat-row span[style*="color:var(--amber)"]');
  if (pendingEl) pendingEl.textContent = d.no_response;

  // Update Donut Chart
  const total = d.total_calls;
  const avail = d.available;
  const notAvail = d.not_available;
  const noResp = d.no_response;
  const C = 2 * Math.PI * 80; // Circumference

  document.getElementById('donut-total').textContent = total;
  document.getElementById('legend-avail').textContent = avail;
  document.getElementById('legend-notavail').textContent = notAvail;
  document.getElementById('legend-noresp').textContent = noResp;

  const elA = document.getElementById('donut-available');
  const elN = document.getElementById('donut-not-available');
  const elR = document.getElementById('donut-no-response');

  if (total === 0) {
    elA.style.strokeDasharray = `0 ${C}`;
    elN.style.strokeDasharray = `0 ${C}`;
    elR.style.strokeDasharray = `0 ${C}`;
    return;
  }

  const pA = avail / total;
  const pN = notAvail / total;
  const pR = noResp / total;

  elA.style.strokeDasharray = `${pA * C} ${C}`;
  elN.style.strokeDashoffset = -pA * C;
  elN.style.strokeDasharray = `${pN * C} ${C}`;
  elR.style.strokeDashoffset = -(pA + pN) * C;
  elR.style.strokeDasharray = `${pR * C} ${C}`;
}

// ===== INITIAL DASHBOARD POPULATION & COUNTER ANIMATION =====
(function(){
  const initialStats = {
    total_contacts: parseInt("{{ contacts|length }}") || 0,
    total_calls: parseInt("{{ logs|length }}") || 0,
    available: parseInt("{{ available_logs|length }}") || 0,
    not_available: parseInt("{{ not_available_logs|length }}") || 0,
    no_response: parseInt("{{ no_response_logs|length }}") || 0,
    success_rate: parseFloat("{% if logs|length > 0 %}{{ ((available_logs|length / logs|length) * 100)|round(1) }}{% else %}0{% endif %}") || 0
  };

  updateDashboardStats(initialStats);

  // Animate numbers on load
  document.querySelectorAll('.card-value, .stat-val').forEach(el => {
    if (el.id === 'ana-rate' || el.textContent.includes('%')) return; // skip percentage
    const target = parseInt(el.textContent) || 0;
    if (target === 0) return;
    let current = 0;
    const step = Math.max(1, Math.ceil(target / 30));
    const interval = setInterval(() => {
      current += step;
      if (current >= target) {
        current = target;
        clearInterval(interval);
      }
      el.textContent = current;
    }, 25);
  });
})();

// ===== AUTO-REFRESH STATS (every 5 seconds) =====
setInterval(() => {
  const token = localStorage.getItem('access_token');
  if (!token) return;
  fetch('/api/stats', {
    headers: { 'Authorization': 'Bearer ' + token }
  })
    .then(r => {
      if (r.status === 401) logout();
      return r.json();
    })
    .then(d => {
      updateDashboardStats(d);
    })
    .catch(() => {});
}, 5000);

// ===== AUTHENTICATION LOGIC =====
function switchAuthView(view) {
  document.querySelectorAll('.auth-tab').forEach(el => el.classList.remove('active'));
  document.querySelectorAll('.auth-view').forEach(el => el.classList.remove('active'));
  
  const tabs = Array.from(document.querySelectorAll('.auth-tab'));
  if(view === 'login') tabs[0].classList.add('active');
  if(view === 'register') tabs[1].classList.add('active');
  if(view === 'demo') tabs[2].classList.add('active');
  if(view === 'otp') tabs[1].classList.add('active'); // OTP keeps register tab active

  document.getElementById('view-' + view).classList.add('active');
}

async function doLogin() {
  const user = document.getElementById('login-user').value;
  const pass = document.getElementById('login-pass').value;
  if(!user || !pass) return showToast('Please enter username and password', 'error');

  try {
    const res = await fetch('/api/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username: user, password: pass })
    });
    const data = await res.json();
    if(res.ok) {
      localStorage.setItem('access_token', data.access_token);
      document.getElementById('auth-overlay').style.display = 'none';
      showToast('Logged in securely as ' + user, 'success');
      // trigger a refresh
      fetch('/api/logs', { headers: { 'Authorization': 'Bearer ' + data.access_token }})
        .then(r=>r.json()).then(d=>updateTables(d.logs)).catch(()=>{});
    } else {
      showToast(data.detail || 'Login failed', 'error');
    }
  } catch(e) {
    showToast('Network error', 'error');
  }
}

async function doSendOTP() {
  const user = document.getElementById('reg-user').value;
  const email = document.getElementById('reg-email').value;
  const pass = document.getElementById('reg-pass').value;
  if(!user || !email || !pass) return showToast('Please fill all fields', 'error');

  const btn = document.querySelector('#view-register .auth-btn');
  btn.textContent = 'SENDING...';
  
  try {
    const res = await fetch('/api/auth/send-otp', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username: user, email: email, password: pass })
    });
    const data = await res.json();
    if(res.ok) {
      showToast('OTP sent to ' + email, 'success');
      switchAuthView('otp');
    } else {
      showToast(data.detail || 'Failed to send OTP', 'error');
    }
  } catch(e) {
    showToast('Network error', 'error');
  } finally {
    btn.textContent = 'SEND OTP';
  }
}

async function doVerifyOTP() {
  const user = document.getElementById('reg-user').value;
  const email = document.getElementById('reg-email').value;
  const pass = document.getElementById('reg-pass').value;
  const otp = document.getElementById('reg-otp').value;
  if(!otp) return showToast('Please enter OTP', 'error');

  try {
    const res = await fetch('/api/auth/verify-otp', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username: user, email: email, password: pass, otp: otp })
    });
    const data = await res.json();
    if(res.ok) {
      localStorage.setItem('access_token', data.access_token);
      document.getElementById('auth-overlay').style.display = 'none';
      showToast('Registration successful! Welcome.', 'success');
      // trigger a refresh
      fetch('/api/logs', { headers: { 'Authorization': 'Bearer ' + data.access_token }})
        .then(r=>r.json()).then(d=>updateTables(d.logs)).catch(()=>{});
    } else {
      showToast(data.detail || 'OTP Verification failed', 'error');
    }
  } catch(e) {
    showToast('Network error', 'error');
  }
}

async function doDemoLogin() {
  // Try to login as guest
  try {
    const res = await fetch('/api/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username: "guest", password: "guestpassword" })
    });
    const data = await res.json();
    if(res.ok) {
      localStorage.setItem('access_token', data.access_token);
      document.getElementById('auth-overlay').style.display = 'none';
      showToast('Logged in as Guest securely', 'success');
    } else {
      showToast('Demo account not configured on backend', 'error');
    }
  } catch(e) {
    showToast('Network error', 'error');
  }
}

function logout() {
  localStorage.removeItem('access_token');
  document.getElementById('auth-overlay').style.display = 'flex';
  showToast('Logged out', 'info');
}

// Check initial auth state
document.addEventListener('DOMContentLoaded', async () => {
  const token = localStorage.getItem('access_token');
  if(token) {
    try {
      const res = await fetch('/api/me', {
        headers: { 'Authorization': 'Bearer ' + token }
      });
      if(res.ok) {
        document.getElementById('auth-overlay').style.display = 'none';
      } else {
        localStorage.removeItem('access_token');
      }
    } catch(e) {
      // Network error, assume logged out
    }
  }
});
</script>
</body>
</html>
