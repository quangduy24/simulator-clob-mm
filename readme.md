# AH Prediction Market — Mô phỏng với line động

Mô phỏng thị trường dự đoán cho kèo châu Á (Asian Handicap) từ **dữ liệu odds thật**
(sample 90 trận EU5 2024-25), line biến động theo từng tick, 4 logic market-maker
chọn được đơn/lẻ hoặc đa (multi-select), hiển thị song song **xác suất ∥ odds decimal**.

Mở trực tiếp (offline, không cần server, không CDN):

```
ah_prediction_simulation.html
```

---

## 1. Dữ liệu: 8 biến trong mỗi file sample

`archive/sample/{EPL,LaLiga,SerieA}/2024-2025/round*_match_*.csv` — 90 trận,
**107.446 dòng** (trung bình ~1.194 dòng/trận), 8 cột:

| # | Biến | Kiểu / VD | Ý nghĩa trong mô phỏng |
|---|------|-----------|------------------------|
| 1 | `Teams` | `伯恩茅斯 vs 埃弗顿` (Bournemouth vs Everton) | Tên tiếng Trung, nhất quán nội bộ. Chỉ dùng làm nhãn + ID (lấy từ tên file). |
| 2 | `FT Score` | `1-0`, `0-5`, `4-1`, `0-6` | **Căn cứ tất toán duy nhất.** Parse `hg-ag`. Sample 90 trận không có blank (full 7.494 trận có ~2% hoãn/hủy → code bỏ qua). |
| 3 | `HT Score` | `0-0`, `2-0`, `0-3` | Chỉ hiển thị bối cảnh, không tham gia settle. |
| 4 | `Bookmaker` | 15 mã (xem §2) | Tách luồng **sharp → fair signal** và **public (HKJC) / rec** để đối chiếu. Đọc bằng `utf-8-sig`. |
| 5 | `Home Odds` | `0.84`, `1.12` | **HK payout** (lợi nhuận / 1u stake), không phải decimal. Tăng = bị đánh ngược. |
| 6 | `Handicap` | `0.75`, `-1.5`, `0.0` (19 giá trị: `-2.0…2.5`) | **Line động.** Mỗi trận có **2–6 line khác nhau** (VD `2591088: 0.5/0.75/1.0`; upload full-tick `2591117: -0.5/0.0/0.25/0.5`). Mỗi tick mang line riêng; vé gắn line lúc vào (§4). Dạng `0.5/1` (full data) parse `(a+b)/2`, giữ dấu (`-0.5/1 → -0.75`). |
| 7 | `Away Odds` | `1.02`, `0.74` | HK payout phía sân khách, dùng chung công thức de-vig. |
| 8 | `Timestamp` | `20250104225637` = `YYYYMMDDHHmmss` UTC | **File gốc lưu giảm dần (dòng 0 = close).** Simulation sort tăng dần để replay open → close. Span ~8 ngày/trận. |

### Thống kê đã đo trên sample

- Tổng dòng theo `Handicap`: `0.0: 9.477`, `0.25: 12.075`, `-0.25: 8.906`, `0.5: 7.132`,
  `-0.5: 9.087`, `0.75: 8.763`, `-0.75: 4.337`, `1.0: 7.517`, `-1.0: 4.618`,
  `1.25: 6.400`, `-1.25: 2.636`, `1.5: 10.148`, `-1.5: 4.200`, `1.75: 6.352`,
  `-1.75: 985`, `2.0: 2.578`, `-2.0: 48`, `2.25: 1.698`, `2.5: 489`.
- Odds HK quan sát: khoảng `0.73 – 1.12`.
- 3 trận demo nhúng sẵn (mỗi trận 120 điểm): pick'em thua (`2591117`, FT `0-2`,
  H `0.25→0.0`), cửa trên thắng sát nút half-win (`2591088`, FT `1-0`, H `0.75`),
  cửa trên chấp sâu thua (`2607056`, FT `1-1`, H `1.5`).

## 2. Bookmaker: 15 mã và vai trò

ASCII: `12*`, `18*`, `36*` (Bet365), `Crow*`, `Interwet*`.
CJK + `*`: `澳*` (U+6FB3, sharp kiểu Pinnacle), `平*` (U+5E73, Pinnacle),
`香港马*` = U+9999 U+6E2F U+9A6C + `*` (HKJC, public), còn lại là các sharp châu Á
(`易* 伟* 利* 明* 盈* 金宝* …`) và rec (`10*` nếu xuất hiện).

Quy tắc fair trong simulation: **loại HKJC + rec (`12*`, `10*`, `Interwet*`)**,
các mã còn lại coi là sharp/reference. Mỗi tick gắn cờ `s ∈ {0,1}`.

## 3. Ba quy ước toán cốt lõi

### 3.1. Dấu handicap: `homeLine = −H`

`H` là cột `Handicap`. Kiểm chứng bằng đội mạnh/yếu:

- AC Milan (chủ, mạnh) vs Cagliari, `H = +1.5` → Milan chấp 1.5 (homeLine `-1.5`).
- Burnley (chủ, yếu) vs Man City, `H = −1.5` → Burnley được chấp (homeLine `+1.5`).
- FT `4-1`, `H = 1.5`: diff `+3`, `3 − 1.5 = 1.25 > 0` → chủ cover ✔.
- FT `0-5`, `H = −0.25`: diff `−5`, `−5 + 0.25 < 0` → chủ thua kèo ✔.

Vậy vé HOME cover khi `(hg − ag) + homeLine > 0`, với `homeLine = −H`.

### 3.2. Odds HK → xác suất de-vig

Odds HK `o < 1` thường xuyên nên không thể là decimal. Quy đổi:

```
decimal d = o + 1
p_home  = (1/d_home) / (1/d_home + 1/d_away)
```

VD tick close West Ham (`0.98 / 0.88`): `d = 1.98 / 1.88`,
`p = 0.5051 / (0.5051 + 0.5319) ≈ 0.487` (test đã assert `0.4870`).
Tổng implied `≈ 1.037` → vig ~3.7%, hợp lý cho AH hai cửa.

### 3.3. Tất toán AH (kể cả quarter-ball)

Với `diff = (hg − ag) + homeLine`, hệ số tất toán `m`:

```
m = +1    nếu diff > +0.25            (win)
m = +0.5  nếu diff = +0.25            (half-win, line quarter)
m =  0    nếu diff = 0                (push, hoàn tiền)
m = −0.5  nếu diff = −0.25            (half-lose)
m = −1    nếu ngược lại               (lose)
```

PnL vé **Back HOME 1u** tại odds HK `o` (decimal `1+o`):

```
PnL = m·o   (m > 0)  ·  half-win chỉ ăn nửa tiền lời
PnL = 0     (m = 0)
PnL = −0.5  (m = −0.5) ·  thua nửa tiền
PnL = −1    (m = −1)
```

VD thật (test đã assert): Bournemouth FT `1-0`, vào H `0.75`
(homeLine `−0.75`): `diff = 1 − 0.75 = 0.25` → half-win. Back `1.89`
(`o = 0.89`) → `PnL = +0.445u` ✔ (khớp số trong simulation).

## 4. Line động và fair signal

Mỗi event là bộ 5 `(t, bookmaker, H(t), homeHK(t), awayHK(t))`.
Không tồn tại "một line của trận đấu": line nhảy 2–6 lần/trận, có khi đi rồi về
(VD `2591088`: open `0.75` → giữa trận có `0.5`, `1.0` → close `0.75`).

- **Vé gắn `H_entry`** (line tại tick vào: Open hoặc tick hiện tại, người dùng chọn),
  settle bằng FT + `H_entry`. Hai vé cùng trận, cùng FT, vào khác thời điểm có thể
  cho PnL khác nhau — đó chính là giá trị của line (CLV thô).
- **Fair `pFair(t)`** = trung vị trượt 9 tick gần nhất của các tick sharp (`s = 1`),
  fallback toàn bộ nếu cửa sổ không có tick sharp. Đường fair trắng trên đồ thị;
  các chấm mờ là từng tick thô (nhảy giữa các nhà là bình thường).

## 5. Bốn logic market-maker (port từ 4 file HTML gốc)

Nút toggle cho phép bật **1 hoặc nhiều** logic để so sánh song song.
Chế độ hiển thị: **Xác suất / Odds decimal / Cả hai**.

Ký hiệu dùng chung cho mọi logic (prob của cửa HOME-cover):
`mid` = giá giữa · `bidP` = MM mua HOME (user Lay) · `askP` = MM bán HOME (user Back) ·
`Back = 1/askP`, `Lay = 1/bidP` (decimal).

### A · Poisson xG (từ `interactive_…_d1f0…`, mặc định bật)

Mô hình tỉ số rời rạc: `K ~ Pois(AxG)`, `M ~ Pois(BxG)` độc lập.

```
P(K=k) = e^(−λ)·λ^k/k!,  k = 0…10
pWin  = Σ P(K=k)·P(M=m)  trên các cặp settleMult(k,m,homeLine) = +1
pHalf = Σ … = +0.5  ·  pPush = Σ … = 0
pCover = pWin + 0.5·pHalf            (half-win tính nửa, push hoàn)
skewOff = −(skew%/100)·0.08  (MM đang ôm HOME thì hạ giá để dụ chiều ngược lại)
mid  = clamp(pCover + skewOff, 0.08, 0.92)
bidP = mid − 0.025   (half-spread 2.5%, tổng 5%)
askP = mid + 0.025
```

Nút **Fit A theo fair**: giữ tổng bàn thắng `S = AxG+BxG`, tìm `d = AxG−BxG`
bằng chia đôi 24 vòng sao cho `pCover((S+d)/2, (S−d)/2) = fair`.
VD đã chạy: fair `0.504` @H `0.75` → `d ≈ +1.08` (dương: chủ mạnh hơn ✔).

### B · Normal μ/σ² (từ `interactive_…_6b16…`)

Hiệu số bàn thắng `D ~ N(μ, σ²)`, Φ là CDF chuẩn (xấp xỉ erf Abramowitz–Stegun):

```
cover ⟺ D + homeLine > 0 ⟺ D > −homeLine
line nguyên/nửa:  p = 1 − Φ(−homeLine; μ, σ)
line quarter (H·2 không nguyên, VD −0.75):
  tách thành homeLine±0.25 (VD −0.5 và −1.0), p = trung bình 2 cửa
margin  = 0.02 + 0.015·variance   (bất định càng lớn, spread càng rộng)
fairOdds = 1/p
bidOdds  = 1/min(p·(1+margin), 0.99)   (user Lay)
askOdds  = 1/max(p·(1−margin), 0.01)   (user Back)
```

Kiểm chuẩn: `μ = 0.7, var = 1.5, H = 0` → `p = Φ(0.7/√1.5) ≈ 0.7162` ✔.

### C · Avellaneda–Stoikov CLOB (từ `interactive_…_819e…`, mặc định bật)

Market-maker né tồn kho. Với fair `p`, tồn kho `q`, e ngại rủi ro `γ`:

```
r  = clamp(p − q·γ·σ², 0.02, 0.98),  σ² = 0.08   (reservation price)
hs = 0.02 + γ·0.1                                 (half-spread)
bestBid = r − hs   ·   bestAsk = r + hs
```

VD: `p = 0.5, q = 40, γ = 0.05` → `r = 0.34` ✔ (ôm nhiều HOME → hạ mid để dụ bán).
Quote C (`bidP/askP` size 50) nằm thật trong sổ YES (ký hiệu ◈).
Nút **Market Buy/Sell** (size 20) đi lệnh MARKET thật vào sổ CLOB (§6):
giá bình quân từ các lượt khớp, **slippage** = `avg − refAsk` khi mua
(`refBid − avg` khi bán, ref = best hiệu dụng gồm cả khớp chéo),
đồng thời cập nhật `q ∓ size` (MM bán → short).

### D · CLOB chuẩn (nâng cấp từ `interactive_…_2b87…`, mặc định bật)

Hai sổ độc lập **YES / NO** (HĐ "HOME cover" / "không cover"), mỗi sổ có
**bids + asks** riêng. Lệnh: `{id, contract, side BUY/SELL, price, size, left,
seq, owner, type LIMIT/MARKET}`.

```
Ưu tiên: giá trước → thời gian (seq) sau.
- BUY: ask thấp nhất trước; SELL: bid cao nhất trước; đồng giá → seq nhỏ trước.
- Khớp chéo bù nhau (cùng side, contract đối — vì YES@p + NO@q = 1.00):
    BUY  YES@p  khớp  BUY  NO@b  ⟺  p + b ≥ 1,  giá khớp (quy về YES) = 1 − b
    SELL YES@p  khớp  SELL NO@a  ⟺  p + a ≥ 1,  giá khớp (quy về YES) = 1 − a
    (đối xứng khi đặt lệnh phía NO)
- Mỗi vòng lặp lấy ứng viên tốt nhất giữa direct và implied theo giá hiệu dụng
  (BUY lấy min, SELL lấy max) → đúng price priority xuyên sổ.
- LIMIT dư ra nằm nghỉ; MARKET ăn tới hết rồi hủy dư.
- Self-trade prevention: bỏ qua lệnh cùng owner khi quét đối ứng.
- Cancel theo id; trade tape (taker→maker, giá, size, tick); vị thế USER
  theo contract (pos.YES / pos.NO).
```

Thanh khoản: lệnh nền **BASE** (3 tầng mỗi phía mỗi sổ quanh fair) +
**quote của các MM đang bật**:
- **MM-A, B, C**: Quote BUY `bidP` / SELL `askP` (size 50, HĐ YES, ký hiệu ◈).
- **MM-D (CLOB MM)**: Quote đa tầng (ladder quoting $k = 1 \dots \text{Levels}$) trên **cả 2 sổ YES và NO**, lệch tồn kho theo $r_D = \text{clamp}(fair - q_D \cdot \gamma_D \cdot 0.08)$, tham số điều chỉnh: $\delta$ (spread), Tầng (levels), Size/tầng, $\gamma$.
- **Ghost Asks (Implied)**: Sổ lệnh tự động tổng hợp thanh khoản chéo (Bid NO $\to$ Ghost Ask YES @ $1-p$; Bid YES $\to$ Ghost Ask NO @ $1-p$) gắn nhãn `Ghost` / `+N 👻` viền nét đứt.
Mỗi tick (nếu checkbox peg bật) làm mới BASE+MM theo fair/H(t) mới,
**giữ nguyên lệnh ★ của USER**. Nút Reset dựng lại toàn bộ sổ.

UI đặt lệnh & MM-D: Param δ/Tầng/Size/γ · HĐ (YES/NO) · Side (BUY/SELL) · Kiểu (LIMIT/MARKET) · Price · Size ·
Place · Hủy theo id · sổ hiển thị gộp theo mức giá (size cộng dồn, ×n lệnh, gắn nhãn MM & Ghost).

### M · Merge Arb (chiến lược Polymarket Y+N=1, mặc định bật)

Desk giữ `Y, N, cash` (khởi split 1000/1000/1000 từ vốn 2000). Luật `1 Yes + 1 No = 1 pUSD` cho 3 việc cùng kho:

```
1 Quote   — bán bộ đắt hơn 1: aY+aN = 1+2δ
2 Merge arb — mua bộ rẻ hơn 1: aY+aN < 1−ε rồi merge
3 Recycle — min(Y,N) cặp → pUSD
```

Giá khớp được `bY,bN,aY,aN`:

```
bY+bN > 1  → bán bộ (spread)   Π = Q·(bY+bN−1)
aY+aN < 1  → mua bộ (arb)     Π = Q·(1−aY−aN)
bY+bN ≤1≤ aY+aN → chỉ quote
```

Vòng vận hành mỗi tick (đúng thứ tự ưu tiên spec §5):

```
1 An toàn: bY≥aY → hủy quote
2 Arb sạch: aY+aN < 1−ε−2·fee và đủ cash → mua Q=min(askY,askN,cash/sum) 2 phía, merge
3 Arb+flatten: |q|>30 và phía thiếu rẻ (a<0.62) → mua đúng phía đó, merge với hàng dư
4 Quote: r = clamp(fair − q·γ·σ²)  (q=Y−N, γ=0.05, σ²=0.08), bY=r−δ, aY=r+δ, bN=1−aY, aN=1−bY
5 Recycle: min(Y,N)>80 → merge min−50 (cap 60)
6 Cắt lệch: |q|>Qmax → MARKET đóng FAK
```

Quote M nằm thật trong sổ 4 phía (YES bid/ask + NO bid/ask, size 50, ◈). Taker arb trả fee, maker được rebate. PnL ngày: `Π_spread+Π_arb+Π_rebate+Π_inv` — thắng khi 3 số đầu > |Π_inv|.

## 6. Depth và Buy/Sell: từ sổ thật

Đồ thị depth vẽ từ **lệnh nghỉ thật trong sổ YES** (cộng dồn size theo mức giá,
bid xanh / ask đỏ), kèm vạch `fair` (trắng) và reservation `r` của C (tím,
ghi cả khoảng `[bidP–askP]`). Sổ trống → hiện thông báo thay vì depth giả.
Nút Market Buy/Sell của panel C thực chất là lệnh MARKET YES size 20 của USER
đi qua đúng `submitClob` (khớp cả direct lẫn implied), nên slippage phản ánh
thanh khoản thật trong sổ tại tick đó.

## 7. Cấu trúc file simulation

```
D:\simulation-prediction-market\
├── ah_prediction_simulation.html   ← file chạy (827 KB, Dark Luxury, offline)
├── data\
│   ├── timelines_all.json          ← 90 trận × 120 điểm (763 KB, nguồn nhúng)
│   └── timelines_demo.json / timelines_meta.json
└── archive\sample\…                ← 90 CSV gốc (upload bất kỳ file nào để replay full-tick)
```

Panel trong HTML: (1) chọn trận + upload CSV · (2) toggle A/B/C/D/M + params ·
(3) playback open→close · đồ thị fair vs MM + line H(t) · 2 sổ YES/NO (bid+ask thật) +
tape + lệnh USER · bot flow 1000 bots · PnL chart-first (equity/bars/inventory, M merge) · depth · HUD · log.

## 8. Bot flow: 1000 bots ngẫu nhiên + bảng lãi MM

### 8.1. Bots

Mặc định app tự tạo **1000 bots (seed 7)** và đặt ON — playback là thấy ngay flow.
Mỗi bot có profile ngẫu nhiên: kiểu (`taker 45% / maker 30% / trend 15% / bias 10%`),
lệch cửa `sideBias ∈ [−1,1]`, size 1–25, xác suất hành động/tick 1–6%.

```
value  (30%): soi edge vs mid; edge <1.8% đứng ngoài, >6.5% MARKET, còn lại LIMIT quanh privateProb
noise  (20%): casual — 55% MARKET, còn LIMIT giá tròn 0.05 như người mới
momentum (20%): theo quán tính 5 tick (|Δ|>0.003), MARKET/LIMIT tùy edge
meanrev  (15%): fade khi lệch xa mid, LIMIT quanh privateProb
scalper  (15%): ăn spread, đặt 2 phía quanh mid, TTL ngắn 6–14 tick
```

Mỗi bot như một **user thật** với bankroll (80–320u), bias niềm tin bền vững (±0.14),
skill và kỷ luật riêng — nhìn sổ (best bid/ask, spread), tính edge = privateProb − mid,
rồi mới chọn MARKET hay LIMIT + giá/size hợp lý (noise hay đặt giá tròn 0.05,
value đặt quanh niềm tin riêng, scalper ăn spread 2 phía, v.v.), và thu nhỏ size
khi đang lệch vị thế nặng. Hướng bull/bear được map **đối xứng YES/NO**
(bull+YES=BUY YES · bull+NO=SELL NO · …) nên sổ luôn cân 4 chiều
(đo 200 bots/120 ticks: `BY 39x/BN 36x/SY 42x/SN 38x` ✔).

Tối đa 60 lệnh/tick (giới hạn hiệu năng). Seed cố định (`mulberry32`) → chạy lại
cho kết quả bit-identical (test assert 2 lần chạy 200 bots/120 ticks ra
`1551 orders / 1443 fills` giống hệt nhau). Mọi bot gom owner **BOTS**;
lệnh LIMIT của bot tự hết hạn (TTL), lệnh USER giữ nguyên.

### 8.2. Tất toán nhị phân phân đoạn (dùng cho PnL)

HĐ YES tất toán theo **close line** `H_close`, hệ số AH `m` (§3.3):

```
P_YES = (m+1)/2  (win 1 · half-win 0.75 · push 0.5 · half-lose 0.25 · lose 0)
P_NO  = 1 − P_YES
```

VD `2591088` (FT `1-0`, close H `0.75` → `m = +0.5`): `P_YES = 0.75` ✔ (test assert).

### 8.3. Bảng lãi (per-owner, từ fills thật) — chart-first

**Trên cùng: 1. Equity curve** (mỗi bên một đường) — `cash + fair·netYES + (1−fair)·netNO`
theo từng tick, tổng mọi bên hằng 0 (zero-sum). Giá trị cuối ghi ở chú giải.

**Giữa: 2. Settled bar chart** — PnL đã tất toán theo close line
(P_YES phân đoạn §8.2), mỗi bên một cột (xanh + / đỏ −, ghi số).

**Dưới: 3. Inventory chart** — tồn kho ròng YES của các MM đang bật (A/B/C)
theo tick — để kiểm chứng thuật toán (dương = MM đang ôm YES, sắp hạ giá `r`).

Mỗi lượt khớp ghi nhận cả 2 phía theo **giá của chính phía đó**
(taker khớp chéo ghi theo giá hiệu dụng, maker ghi theo giá resting của mình —
tổng khóa luôn `1.00×q`). Mỗi bên mỗi contract theo dõi mua (qty, cost) và bán
(qty, revenue); test assert tay: USER mua 10 YES @0.6 → settled `−6 + 0.75×10 = +1.5` ✔.

```
cash    = Σ (sellRev − buyCost)
settled = cash + P_YES·netYES + P_NO·netNO
MTM     = cash + last·netYES + (1−last)·netNO   (last = giá khớp gần nhất)
```

Bảng hiện Fills · Vol · Net YES/NO · Cash · MTM · Settled cho từng owner
(`MM-A/B/C/M`, `BASE` fallback, `BOTS`, `USER`) — đặt **sau** 3 biểu đồ nêu trên.
M với `Y,N,cash` riêng (init 1000/1000/1000) nên equity = `cash+f·Y+(1−f)·N−2000`.
Bên dưới là **plot equity** và **plot tồn kho ròng YES của các MM (gồm M)**.

### 8.4. Kiểm chứng thuật toán MM bằng bot flow (kết quả đo thật)

Giao diện Dark Luxury: PnL **plot trước, bảng sau** — mở app là thấy ngay ai lãi.

Thanh khoản chính là quote của các MM đang bật (BASE chỉ fallback),
nên bot giao dịch **trực tiếp** với MM:

- MM-A chưa cân (mid 0.42 vs fair 0.50): bot BUY nhấc ask rẻ → **net −4914**;
  MM-C ôm hàng **+2479**, 564 fills với bots; Σ equity =0 ✔ (adverse selection).
- **M merge arb** sống nhờ sổ lệch khỏi 1: khi `aY+aN<1−ε` (VD 0.39+0.58=0.97) thì
  mua bộ 30 @0.97, merge lấy 30, lãi `30·0.03=0.9u` tức thì; khi dư Yes (q>30) thì
  chỉ mua No rẻ để vừa arb vừa cân kho; đủ cặp thì recycle lấy cash.

Dùng **Fit A/B** (B: μ≈0.76 khớp fair 0.503) để cân MM về fair rồi chạy bots —
quan sát spread capture và tồn kho M dao động quanh 0.

## 9. Kiểm thử đã chạy (node, số thật)

- `devig(0.98, 0.88) = 0.4870` · `modelB(0.7,1.5,0) = 0.7162` ·
  `modelC(0.5,40,0.05): r = 0.34` · settle 5 trường hợp (win/half/push/half/lose) ✔
- **CLOB engine: 12 nhóm unit test pass** — nghỉ lệnh, quét đa tầng đúng giá,
  time-priority đồng giá, partial fill, khớp chéo implied 2 chiều, direct thắng
  implied khi rẻ hơn, không khớp khi p+q<1, self-trade prevention, cancel
  (kể cả id lạ → false), market quét + hủy dư, khớp phía NO, best bid/ask ✔
- DOM-stub headless: init → step → đặt lệnh CLOB → Buy/Sell C (MARKET thật vào sổ) →
  tất toán vé (`Back 1.89 @H=0.75, FT 1-0 → HALF-WIN +0.445u`) → Fit A (`d ≈ +1.08`) →
  upload CSV thật (`2591117`: 975 ticks, 4 line) ✔
- Bắt và sửa được 3 bug nhờ test: lỗi syntax template, **truyền nhầm dấu H
  (cột H thay vì homeLine = −H)** vào model A/B, sót biến sau refactor D.
- **Bots + PnL + plot: 20 assert pass** (+ **M 7 assert** riêng) — payout phân đoạn,
  hạch toán, TTL, determinism, đối xứng 4 chiều, chạm quote A/C, zero-sum, Fit B,
  và **M: init split, quote 4 phía, arb sạch, no-arb, flatten, recycle, equity**.
  Tổng 27 nhóm đã xanh.

## 10. Giới hạn đã biết & bước tiếp theo (mục 5, để sau)

- Timeline nhúng là 120 điểm/trận (đủ mượt để hiểu hệ thống); upload CSV cho
  full-tick khi cần chi tiết.
- Fair hiện dùng trailing-median sharp; bản backtest nên dùng consensus theo
  timestamp đồng bộ + tách riêng HKJC-public divergence.
- Chưa có backtest 90 trận (CLV/calibration/PnL tổng hợp) — theo yêu cầu, để sau
  khi đã hiểu hệ thống qua simulation này.
