document.addEventListener('DOMContentLoaded', () => {
  const API_BASE = 'http://localhost:8000/api';

  const btnRunBacktest = document.getElementById('btn-run-backtest');
  const btnTestTelegram = document.getElementById('btn-test-telegram');
  const telegramBadge = document.getElementById('telegram-badge');

  fetchConfig();
  loadOpsJournal();

  btnRunBacktest.addEventListener('click', runBacktest);
  btnTestTelegram.addEventListener('click', testTelegram);
  const btnOpsRefresh = document.getElementById('btn-ops-refresh');
  if (btnOpsRefresh) btnOpsRefresh.addEventListener('click', loadOpsJournal);

  async function loadOpsJournal() {
    const tbody = document.getElementById('ops-tbody');
    if (!tbody) return;
    try {
      const res = await fetch(`${API_BASE}/journal/today`);
      if (!res.ok) throw new Error('journal unavailable');
      const data = await res.json();
      document.getElementById('ops-proposed').innerText = data.proposed || 0;
      document.getElementById('ops-taken').innerText = data.taken || 0;
      document.getElementById('ops-skipped').innerText = data.skipped || 0;
      document.getElementById('ops-wins').innerText = data.wins || 0;
      document.getElementById('ops-losses').innerText = data.losses || 0;
      document.getElementById('ops-wr').innerText = `${data.win_rate_pct || 0}%`;
      const trades = data.trades || [];
      if (!trades.length) {
        tbody.innerHTML = '<tr><td colspan="9" class="text-center empty-msg">No journal rows for today.</td></tr>';
        return;
      }
      tbody.innerHTML = '';
      trades.forEach(t => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
          <td>${t.entry_time || ''}</td>
          <td><strong>${t.pair || ''}</strong></td>
          <td>#${t.setup_id || ''} ${t.setup_name || ''}</td>
          <td>${t.direction || ''}</td>
          <td>${t.status || ''}</td>
          <td>${t.outcome || ''}</td>
          <td>${t.reason_code || ''}</td>
          <td>${t.note || ''}</td>
          <td class="ops-actions">
            <button data-act="TAKEN" data-id="${t.id}">Taken</button>
            <button data-act="SKIPPED" data-id="${t.id}">Skip</button>
            <button data-act="WIN" data-id="${t.id}">Win</button>
            <button data-act="LOSS" data-id="${t.id}">Loss</button>
          </td>`;
        tbody.appendChild(tr);
      });
      tbody.querySelectorAll('button[data-act]').forEach(btn => {
        btn.addEventListener('click', async () => {
          const id = btn.getAttribute('data-id');
          const act = btn.getAttribute('data-act');
          const body = {};
          if (act === 'TAKEN' || act === 'SKIPPED') body.status = act;
          if (act === 'WIN' || act === 'LOSS') body.outcome = act;
          if (act === 'WIN' || act === 'LOSS') {
            const note = prompt('Optional note:');
            if (note) body.note = note;
          }
          await fetch(`${API_BASE}/journal/trades/${id}`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body)
          });
          loadOpsJournal();
        });
      });
    } catch (e) {
      tbody.innerHTML = '<tr><td colspan="9" class="text-center empty-msg">Journal offline — start API server.</td></tr>';
    }
  }

  async function fetchConfig() {
    try {
      const res = await fetch(`${API_BASE}/config`);
      if (res.ok) {
        const cfg = await res.json();
        if (cfg.telegram) {
          document.getElementById('input-telegram-token').value = cfg.telegram.bot_token || '';
          document.getElementById('input-telegram-chatid').value = cfg.telegram.chat_id || '';
          if (cfg.telegram.enabled && cfg.telegram.bot_token && cfg.telegram.bot_token !== 'YOUR_TELEGRAM_BOT_TOKEN') {
            telegramBadge.innerText = 'Telegram: Connected';
            telegramBadge.className = 'badge badge-success';
          } else {
            telegramBadge.innerText = 'Telegram: Unconfigured';
            telegramBadge.className = 'badge badge-info';
          }
        }
      }
    } catch (err) {
      console.warn('Backend server standby mode.');
      telegramBadge.innerText = 'Telegram: Standby';
    }
  }

  async function runBacktest() {
    btnRunBacktest.disabled = true;
    btnRunBacktest.innerText = '⏳ Running 10-Setup Backtest...';

    const capital = parseFloat(document.getElementById('input-capital').value) || 200.0;
    const risk = parseFloat(document.getElementById('input-risk').value) || 1.0;
    const rr = parseFloat(document.getElementById('input-rr').value) || 2.0;
    const slippage = parseFloat(document.getElementById('input-slippage').value) || 0.5;
    const commission = parseFloat(document.getElementById('input-commission').value) || 3.50;

    const selectedPairs = Array.from(document.querySelectorAll('.pair-chk:checked')).map(c => c.value);

    const payload = {
      pairs: selectedPairs.length ? selectedPairs : ['GBPUSD', 'EURUSD'],
      timeframe: '5m',
      starting_balance: capital,
      risk_percent: risk,
      min_rr: rr,
      max_slippage_pips: slippage,
      commission_per_lot: commission
    };

    try {
      const res = await fetch(`${API_BASE}/backtest`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      if (res.ok) {
        const data = await res.json();
        updateDashboard(data);
      } else {
        alert('Backtest failed. Ensure FastAPI server is running on http://localhost:8000.');
      }
    } catch (err) {
      alert('Cannot connect to backend server. Run "python run_live_monitor.py".');
    } finally {
      btnRunBacktest.disabled = false;
      btnRunBacktest.innerText = '🚀 Run 10-Setup Backtest';
    }
  }

  function updateDashboard(data) {
    const overall = data.overall || {};
    document.getElementById('val-capital').innerText = `$${overall.starting_balance || 200.0}`;
    document.getElementById('val-total-trades').innerText = overall.total_trades || 0;
    document.getElementById('val-win-rate').innerText = `${overall.win_rate_pct || 0}%`;
    document.getElementById('val-win-loss-count').innerText = `${overall.winning_trades || 0} Wins / ${overall.losing_trades || 0} Losses`;
    
    const profit = overall.total_net_profit || 0;
    document.getElementById('val-net-profit').innerText = `$${profit >= 0 ? '+' : ''}${profit.toLocaleString()}`;
    const retPct = ((profit / (overall.starting_balance || 200.0)) * 100).toFixed(2);
    document.getElementById('val-return-pct').innerText = `${retPct >= 0 ? '+' : ''}${retPct}% Net Return`;

    // Update ALL 10 Setup Cards
    const setups = data.by_setup || [];
    setups.forEach(s => {
      const id = s.setup_id;
      const tEl = document.getElementById(`s${id}-trades`);
      const wEl = document.getElementById(`s${id}-winrate`);
      const pEl = document.getElementById(`s${id}-pnl`);

      if (tEl) tEl.innerText = s.trades;
      if (wEl) wEl.innerText = `${s.win_rate}%`;
      if (pEl) pEl.innerText = `$${s.net_pnl.toLocaleString()}`;
    });

    // Populate Trades Table
    const tbody = document.getElementById('trades-tbody');
    tbody.innerHTML = '';

    let allTrades = [];
    if (data.by_pair) {
      Object.values(data.by_pair).forEach(p => {
        if (p.trades) allTrades = allTrades.concat(p.trades);
      });
    }

    allTrades.sort((a, b) => new Date(b.timestamp_entry) - new Date(a.timestamp_entry));
    document.getElementById('trade-count-badge').innerText = `${allTrades.length} trades`;

    if (allTrades.length === 0) {
      tbody.innerHTML = '<tr><td colspan="9" class="text-center empty-msg">No trades generated for selected criteria.</td></tr>';
      return;
    }

    allTrades.slice(0, 100).forEach(t => {
      const tr = document.createElement('tr');
      const dirBadge = t.direction === 'BUY' ? '<span class="badge-buy">BUY</span>' : '<span class="badge-sell">SELL</span>';
      const pnlColor = t.net_pnl >= 0 ? 'highlight-green' : 'highlight-red';

      tr.innerHTML = `
        <td>${t.timestamp_entry}</td>
        <td><strong>${t.pair}</strong></td>
        <td>#${t.setup_id} ${t.setup_name}</td>
        <td>${dirBadge}</td>
        <td>${t.entry_price}</td>
        <td>${t.sl_price}</td>
        <td>${t.tp_price}</td>
        <td><strong class="${pnlColor}">${t.outcome}</strong></td>
        <td class="${pnlColor}"><strong>$${t.net_pnl > 0 ? '+' : ''}${t.net_pnl}</strong></td>
      `;
      tbody.appendChild(tr);
    });
  }

  async function testTelegram() {
    const token = document.getElementById('input-telegram-token').value;
    const chatid = document.getElementById('input-telegram-chatid').value;

    if (!token || !chatid) {
      alert('Please enter your Telegram Bot Token and Chat ID.');
      return;
    }

    btnTestTelegram.disabled = true;
    btnTestTelegram.innerText = '📲 Sending Telegram Signal...';

    try {
      const res = await fetch(`${API_BASE}/telegram/test`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ bot_token: token, chat_id: chatid })
      });

      if (res.ok) {
        alert('Success! Check your Telegram chat for the test notification.');
        telegramBadge.innerText = 'Telegram: Connected';
        telegramBadge.className = 'badge badge-success';
      } else {
        const err = await res.json();
        alert(`Error sending Telegram message: ${err.detail || 'Invalid token/chat ID'}`);
      }
    } catch (e) {
      alert('Backend server not connected. Start server with "python run_live_monitor.py".');
    } finally {
      btnTestTelegram.disabled = false;
      btnTestTelegram.innerText = '📲 Send Test Telegram Signal';
    }
  }
});
