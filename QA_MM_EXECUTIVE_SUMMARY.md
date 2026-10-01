# TỔNG HỢP KỸ THUẬT: 5 THUẬT TOÁN MM & ĐỐI CHIẾU PLAN MVB 3 THÁNG

> Đối chiếu mã nguồn: [ah_prediction_simulation.html](file:///d:/Okas/okas-source/simulator-clob-mm/ah_prediction_simulation.html) · Báo cáo chi tiết: [QA_MM_DETAILED_METRICS.md](file:///d:/Okas/okas-source/simulator-clob-mm/QA_MM_DETAILED_METRICS.md)

---

## 1. THUẬT TOÁN CỐT LÕI MVB (THÁNG 1 - 2)

### 1.1. Model D: CLOB Multi-Level Ladder & Dual Orderbook
*Báo giá 3 tầng (L1–L3) 4 phía đối ứng bảo toàn chẵn lẻ nhị phân `YES + NO = 1.00`.*

* **Tham số cấu hình (`CONFIG.MODELS.D`):**
  | Biến | Kiểu | Giá trị | Ý nghĩa kỹ thuật |
  | :--- | :--- | :--- | :--- |
  | `DEF_DELTA` | `number` | `0.02` | Bước giá phân tầng spread ($\Delta$) |
  | `DEF_LEVELS` | `number` | `3` | Số tầng báo giá mỗi bên ($k \in \{0, 1, 2\}$) |
  | `DEF_SIZE` | `number` | `40` | Khối lượng đặt tại mỗi tầng |
  | `DEF_GAMMA` | `number` | `0.04` | Hệ số phạt lệch tồn kho |
  | `SKEW_SCALE` | `number` | `0.08` | Độ nhạy điều chỉnh giá theo tồn kho |

* **Trạng thái & Logic tính toán (`postClobQuotes` / `modelD`):**
  ```javascript
  // 1. Tính tồn kho ròng và reservation price r:
  const qD = (pD.YES.b - pD.YES.s) - (pD.NO.b - pD.NO.s);
  const r = clamp(fair - qD * gamma * SKEW_SCALE, 0.03, 0.97);

  // 2. Ladder 4 phía (Bids/Asks YES & NO):
  for (let k = 0; k < levels; k++) {
    const off = delta * (k + 1);
    const by = clamp(r2(r - off), 0.01, 0.99), ay = clamp(r2(r + off), 0.01, 0.99);
    bidsY.push(by); asksY.push(ay);
    bidsN.push(clamp(r2(1 - ay), 0.01, 0.99)); // b_N = 1 - a_Y (Ghost asks)
    asksN.push(clamp(r2(1 - by), 0.01, 0.99)); // a_N = 1 - b_Y
  }
  // Invariant xác thực: b_Y(k) + a_N(k) === 1.00 && a_Y(k) + b_N(k) === 1.00
  ```

---

### 1.2. Model M: Merge Arbitrage Desk & Capital Recycling
*Săn lệch giá xuyên cặp (Clean Merge Arb) và hoàn vốn tiền mặt theo chuẩn CTF.*

* **Tham số cấu hình (`CONFIG.MODELS.M`):**
  | Biến | Kiểu | Giá trị | Ý nghĩa kỹ thuật |
  | :--- | :--- | :--- | :--- |
  | `DEF_CASH` / `initCash` | `number` | `2000` | Vốn khởi tạo (Split 50/50: 1000 cash + 1000 Y/N) |
  | `DEF_DELTA` / `DEF_EPS` | `number` | `0.02` / `0.01` | Half-spread quote / Ngưỡng tối thiểu kích hoạt Arb |
  | `DEF_FEE` / `DEF_REBATE`| `number` | `0.003` / `0.001`| Phí giao dịch taker (0.3%) / Rebate maker (0.1%) |
  | `MAX_ARB_QTY` | `number` | `50` | Size trần cho mỗi lệnh Merge Arb |
  | `IMBALANCE_TRIGGER` | `number` | `30` | Ngưỡng kích hoạt mua bù lệch kho $\|q\| > 30$ |
  | `CHEAP_PRICE_CEIL` | `number` | `0.62` | Giá trần để mua token gom bộ |
  | `RECYCLE_TRIGGER` / `CHUNK` | `number` | `80` / `60` | Điều kiện recycle ($\min(Y,N) > 80$) / Size mỗi đợt rút |
  | `DEF_QMAX` | `number` | `400` | Giới hạn rủi ro tồn kho tối đa trước khi cut market |

* **Luồng thực thi (`runMergeDesk`):**
  ```javascript
  // BƯỚC 1: Self-cross safety
  if (bY >= aY || bN >= aN) { dropOwner("MM-M"); return; }

  // BƯỚC 2: Clean Merge Arbitrage
  const sumA = aY + aN;
  if (sumA < 1 - d.eps - d.fee * 2) {
    const Q = Math.min(szY, szN, Math.floor(d.cash / (sumA + d.fee * 2)), 50);
    submitClob("YES", "BUY", aY, Q, "MARKET", "MM-M");
    submitClob("NO",  "BUY", aN, Q, "MARKET", "MM-M");
    recycleDeskTokens(d, filled); // d.Y -= filled; d.N -= filled; d.cash += filled;
    d.arbPnL += filled * (1 - sumA) - filled * d.fee * 2;
  }

  // BƯỚC 3: Cân kho (Flatten khi q = d.Y - d.N lệch)
  if (q > 30 && aN < 0.62) { /* Mua NO gom bộ */ }
  else if (q < -30 && aY < 0.62) { /* Mua YES gom bộ */ }

  // BƯỚC 4: Tái chế (Recycle ra cash)
  if (Math.min(d.Y, d.N) > 80) recycleDeskTokens(d, Math.min(Math.min(d.Y, d.N) - 50, 60));

  // BƯỚC 5: Cắt lệch vị thế khẩn cấp
  if (Math.abs(q) > d.Qmax) submitClob("YES", side, px, need, "MARKET", "MM-M");
  ```

---

## 2. CÁC MODEL NHÁNH R&D (GIAI ĐOẠN 2)

*Duy trì mô phỏng kiểm chuẩn lý thuyết; chưa đưa vào production MVB.*

| Model | Tham số chính | Công thức định giá cốt lõi | Hiện trạng & Rủi ro |
| :--- | :--- | :--- | :--- |
| **Model A** *(Poisson xG)* | `MAX_K = 10`<br>`HALF_SPREAD = 0.025`<br>`SKEW_SCALE = 0.08` | $\text{fair} = \sum_{k=0}^{10}\sum_{m=0}^{10} \text{Poi}(k; \lambda_A)\text{Poi}(m; \lambda_B) \cdot \text{settleMult}(k, m, hl)$<br>`bidP = mid - 0.025`, `askP = mid + 0.025` | **Cần calibrate:** `fitA()` làm tròn 1 chữ số gây lệch fair `0.0186`. Cần full precision state. |
| **Model B** *(Normal Diff)* | `BASE_MARGIN = 0.02`<br>`VAR_SCALE = 0.015`<br>$\mu = 0.7, \sigma^2 = 1.5$ | $\text{margin} = 0.02 + 0.015 \cdot \sigma^2$<br>$p = \Phi\left(\frac{hl - \mu}{\sigma}\right)$ (kèo đơn) | **BLOCKER (Bug B0):** Đảo dấu `bidP > askP`. Tuyệt đối chưa kích hoạt production. |
| **Model C** *(Avellaneda-Stoikov)* | `SKEW_SCALE = 0.08`<br>`BASE_HS = 0.02`<br>`GAMMA_SCALE = 0.1` | $r = \text{clamp}(\text{fair} - q \cdot \gamma \cdot 0.08, 0.02, 0.98)$<br>$\text{hs} = 0.02 + \gamma \cdot 0.1$<br>`bid = r - hs`, `ask = r + hs` | **Cần fix ledger:** Biến `S.inv` không đồng bộ với Fill Ledger của `submitClob`. |

---

## 3. BẢNG MÃ LỖI, BIẾN LIÊN QUAN & CODE SỬA

### Bug 1: Crossed Book (`Best Bid > Best Ask`) làm tê liệt Model M
* **Biến liên quan:** `S.book.YES.bids[0].price`, `S.book.YES.asks[0].price`, `modelA().askP`, `modelD().bidP`.
* **Nguyên nhân:**
  * `MM-A` mặc định (`axg = 1.8, bxg = 1.1`) quote `askP = 0.44`.
  * `MM-D` neo theo fair (`0.489`) quote `bidP = 0.47`.
  * Push trực tiếp mảng `S.book` không qua matching $\rightarrow$ `Bid (0.47) > Ask (0.44)`.
  * `runMergeDesk()` phát hiện `bY >= aY` kích hoạt `dropOwner("MM-M")` $\rightarrow$ hủy toàn bộ lệnh Model M.
* **Code sửa:**
  ```javascript
  // Fix 1: Tự động chạy fitA khi nạp trận để kéo axg, bxg khớp fair thị trường
  function initMatchState() {
    // ...
    fitA(); 
    refreshLiq(fairAt(0));
  }

  // Fix 2: Trên Backend, mọi order entry bắt buộc qua matching triệt tiêu crossing trước khi resting:
  if (side === "BUY" && price >= effAsk) matchImmediately();
  ```

---

### Bug 2: `fitA()` & `fitB()` đổi tham số nhưng lệnh resting không đổi (Stale Book)
* **Biến liên quan:** `DOM.setVal("axg")`, `DOM.setVal("bxg")`, `DOM.setVal("mu")`, `S.book`.
* **Nguyên nhân:** Sau khi giải nghiệm bisection, hàm chỉ set value DOM và `renderAll()`, thiếu gọi `refreshLiq()`.
* **Code sửa:**
  ```diff
   function fitA() {
     // ... solver d ...
     DOM.setVal("axg", r2((s + d) / 2).toFixed(1));
     DOM.setVal("bxg", r2((s - d) / 2).toFixed(1));
  +  if (S.peg) refreshLiq(fairAt(S.idx));
     renderAll();
   }

   function fitB() {
     // ... solver mu ...
     DOM.setVal("mu", mu);
  +  if (S.peg) refreshLiq(fairAt(S.idx));
     renderAll();
   }
  ```

---

### Bug 3: Model B bị đảo chiều Bid/Ask (`bidP > askP`)
* **Biến liên quan:** `modelB().bidP`, `modelB().askP`, `margin`.
* **Nguyên nhân:** `bidO = 1 / (p * (1 + margin))` $\rightarrow$ `bidP = 1 / bidO = p * (1 + margin) > p` (Bid cao hơn Ask).
* **Code sửa:**
  ```diff
   function modelB(mu, vr, hl) {
     // ...
     const margin = cfg.BASE_MARGIN + cfg.VAR_SCALE * vr;
  -  const bidO = 1 / Math.min(p * (1 + margin), 0.99);
  -  const askO = 1 / Math.max(p * (1 - margin), 0.01);
  -  return { mid: p, back: askO, lay: bidO, bidP: 1 / bidO, askP: 1 / askO };
  +  const bidP = clamp(r2(p * (1 - margin)), cfg.CLAMP_MIN, cfg.CLAMP_MAX);
  +  const askP = clamp(r2(p * (1 + margin)), cfg.CLAMP_MIN, cfg.CLAMP_MAX);
  +  return { mid: p, bidP: bidP, askP: askP, back: 1 / askP, lay: 1 / bidP };
   }
  ```

---

### Bug 4: Model C không đồng bộ Inventory từ Fill Engine
* **Biến liên quan:** `S.inv`, `S.pnl["MM-C"]`.
* **Nguyên nhân:** Panel C dùng `S.inv`, nhưng `submitClob` khớp lệnh bot chỉ ghi vào `S.pnl["MM-C"]`.
* **Code sửa:**
  ```diff
   function getInventoryC() {
  -  return S.inv;
  +  const p = S.pnl["MM-C"];
  +  return p ? (p.YES.b - p.YES.s) : 0;
   }
  ```

---

## 4. CHECKLIST KỸ THUẬT BACKEND PLUGIN (THÁNG 1 - 2 MVB)

1. **Interface `ModelDQuoter`:**
   * Input: `fairPrice: decimal`, `inventory: decimal`, `delta: decimal = 0.02`, `levels: int = 3`.
   * Output: `OrderList [Buy/Sell YES, Buy/Sell NO]` bảo đảm bất biến $P_{\text{YES}} + P_{\text{NO}} = 1.00$.
2. **Interface `MergeArbitrageDesk`:**
   * State: `cashBalance: decimal`, `lockedYES: decimal`, `lockedNO: decimal`.
   * Execution: Quét orderbook $\rightarrow$ Atomic execute cặp lệnh `BUY YES + BUY NO` $\rightarrow$ invoke `mergeTokens()` hoàn vốn về cash.
