BÁO CÁO THẨM ĐỊNH KỸ THUẬT & ĐO LƯỜNG THÔNG SỐ CHI TIẾT 5 THUẬT TOÁN MARKET MAKER (SIMULATION CLOB)

- Dự án: OKAS Prediction Market / Asian Handicap CLOB Simulation
- Tập dữ liệu nguồn: EU5 Asian Handicap Odds Time-Series (90 trận mẫu, 107.446 dòng snapshot thật)
- Phạm vi replay có số liệu chi tiết trong báo cáo: 3 trận EPL; 90 trận chưa được chứng minh đã replay/assert đầy đủ trong artifact hiện tại
- Ngày thực hiện: 30/09/2026
- Trạng thái: Đã hoàn tất QA prototype/UI cho các luồng chính; CHƯA sẵn sàng production do còn blocker về Model B, inventory C, settlement AH và execution Model M

---

MỤC LỤC
1. Kiểm chuẩn nền tảng toán học & Quy ước cốt lõi
2. Chi tiết tham số & Đo lường Model A - Poisson xG
3. Chi tiết tham số & Đo lường Model B - Normal Goal-Difference Model
4. Chi tiết tham số & Đo lường Model C - Inventory Skew (A-S-Inspired)
5. Chi tiết tham số & Đo lường Model D - CLOB Multi-Level Ladder & Dual Orderbook
6. Chi tiết tham số & Đo lường Model M - Merge Arbitrage Desk (CTF-Style)
7. Kiểm thử Engine Khớp lệnh CLOB & Implied Matching (Ghost Asks)
8. Đo lường Replay dòng thời gian trên 3 trận thực tế
9. Tổng hợp các lỗi phát hiện (Bugs & Anomalies Log)

---

1. KIỂM CHUẨN NỀN TẢNG TOÁN HỌC & QUY ƯỚC CỐT LÕI

1.1. Công thức De-vig (Odds HK sang Decimal và Xác suất thực)
- Công thức:
  decimal d = o_HK + 1
  p_fair = (1 / d_home) / (1 / d_home + 1 / d_away)
- Kết quả đo lường Playwright:
  + Case West Ham (hh = 0.98, ha = 0.88):
    - d_home = 1.98, d_away = 1.88
    - p_home = 0.4870466321243523 (Assert chuẩn xấp xỉ 0.4870). PASS.
    - Margin nhà cái (vig) xấp xỉ 3.73%.
  + Case Kèo lệch (hh = 0.84, ha = 1.12):
    - p_home = 0.5353535353535354. Vig xấp xỉ 1.52%. PASS.

1.2. Hàm Tính Hệ Số Tất Toán Asian Handicap (settleMult)
- Quy ước: diff = (hg - ag) + homeLine (với homeLine = -H).
- Kết quả đo lường từng kịch bản:
  + Kịch bản 1: Full-Win
    - Tỉ số: 2 - 0, Handicap H = 1.0 (homeLine = -1.0), diff = +1.00.
    - Kết quả hàm: 1.0 (Kỳ vọng: +1). Đánh giá: PASS.
  + Kịch bản 2: Half-Win (Kèo Quarter)
    - Tỉ số: 1 - 0, Handicap H = 0.75 (homeLine = -0.75), diff = +0.25.
    - Kết quả hàm: 0.5 (Kỳ vọng: +0.5). Đánh giá: PASS.
  + Kịch bản 3: Push (Hòa kèo)
    - Tỉ số: 1 - 0, Handicap H = 1.0 (homeLine = -1.0), diff = 0.00.
    - Kết quả hàm: 0.0 (Kỳ vọng: 0). Đánh giá: PASS.
  + Kịch bản 4: Half-Loss (Kèo Quarter)
    - Tỉ số: 0 - 0, Handicap H = 0.25 (homeLine = -0.25), diff = -0.25.
    - Kết quả hàm: -0.5 (Kỳ vọng: -0.5). Đánh giá: PASS.
  + Kịch bản 5: Full-Loss
    - Tỉ số: 0 - 2, Handicap H = 1.0 (homeLine = -1.0), diff = -3.00.
    - Kết quả hàm: -1.0 (Kỳ vọng: -1). Đánh giá: PASS.

1.3. Phân phối Chuẩn Tích lũy (ncdf & erf)
- Kết quả xấp xỉ Abramowitz & Stegun:
  + z = 0.0 -> ncdf(0, 0, 1) = 0.5000000005 (Sai số < 10^-9). PASS.
  + z = +1.0 -> ncdf(1, 0, 1) = 0.8413447362 (Lý thuyết: 0.841345). PASS.
  + z = -1.0 -> ncdf(-1, 0, 1) = 0.1586552638 (Đối xứng hoàn hảo: 1 - 0.841345). PASS.

1.4. Phân phối Poisson (pois(lambda, k))
- Chữ ký hàm: pois(l, k) với l = lambda, k = số bàn thắng.
- Kết quả đo lường với lambda = 1.8:
  + k = 0 -> P(K=0) = e^-1.8 = 0.16529888822158653. PASS.
  + k = 1 -> P(K=1) = 1.8 * e^-1.8 = 0.2975379987988558. PASS.
  + k = 2 -> P(K=2) = (1.8^2 / 2) * e^-1.8 = 0.2677841989189702. PASS.

1.5. Blocker về Quy ước Settlement/Payout AH
- Hàm settleMult trả về 5 mức: +1, +0.5, 0, -0.5, -1.
- Hàm payoutYES trong simulation ánh xạ thành payout token YES: 1, 0.75, 0.5, 0.25, 0.
- Trong module AH-MVP của repo Backend/frontend hiện tại, half-win được phân loại outcome = Yes, half-loss = No và push = Void; chưa có cùng semantics payout 0.75/0.25 như simulation.
- Hệ quả: Các phép tính fair/PnL có thể đúng theo simulation nhưng chưa chắc đúng với market contract thực tế.
- Kết luận: Phải chốt một specification duy nhất cho settlement trước khi xác nhận Model A/B và PnL là production-correct. Đây là blocker mức Critical.

---

2. CHI TIẾT THAM SỐ & ĐO LƯỜNG MODEL A - POISSON xG

2.1. Cấu hình tham số mặc định
- CONFIG.MODELS.A.MAX_K = 10 (Vòng lặp tính xác suất tỉ số từ 0-0 đến 10-10).
- CONFIG.MODELS.A.HALF_SPREAD = 0.025 (Spread 5% -> Bid -2.5%, Ask +2.5%).
- CONFIG.MODELS.A.SKEW_SCALE = 0.08.
- CONFIG.MODELS.A.CLAMP_MIN = 0.02, CLAMP_MAX = 0.98.

2.2. Đo lường giá trị tính toán
- Thiết lập: Match 0 (H = 0.75 -> homeLine = -0.75), AxG = 1.8, BxG = 1.1, Skew = 0%.
  + p_Win = 0.3541
  + p_Half = 0.1218
  + p_Push = 0.1342
  + p_Cover = p_Win + 0.5 * p_Half = 0.4150
  + Mid Price: 0.4150
  + Bid Price: 0.4150 - 0.025 = 0.3900 -> Odds Lay = 1 / 0.3900 = 2.564
  + Ask Price: 0.4150 + 0.025 = 0.4400 -> Odds Back = 1 / 0.4400 = 2.273

2.2.1. Giới hạn của fair hiện tại
- modelA đang tính fair = p_FullWin + 0.5 * p_HalfWin và không cộng payout của Push/Half-Loss.
- Nếu token YES thực sự payout 1 / 0.75 / 0.5 / 0.25 / 0 như payoutYES(), fair phải là kỳ vọng của toàn bộ 5 trạng thái, không phải công thức hiện tại.
- Nếu market là binary Yes/No/Void, cần định nghĩa lại cách quarter-line resolve thay vì dùng payout phân đoạn.
- Ma trận chỉ chạy đến 10 bàn mỗi đội và không chuẩn hóa phần tail probability còn lại. Sai số thường nhỏ với xG bóng đá thông thường nhưng cần có test/tolerance rõ ràng.

2.3. Kiểm thử thuật toán fitA() (Bisection Solver)
- Mục tiêu: Giữ tổng S = AxG + BxG = 2.9, tìm chênh lệch bàn thắng d = AxG - BxG trên đoạn [-2, 2] sao cho p_Cover(d) = p_fair = 0.4894.
- Kết quả thực thi trên Playwright:
  + d tìm được: +1.02
  + Cập nhật input: AxG = 2.0, BxG = 0.9.
  + Giá fair Model A sau khi fit và làm tròn input: 0.5080 so với fair thị trường 0.4894 (lệch khoảng 0.0186 hay 1.86 điểm phần trăm).
  + Kết luận: Bisection nội bộ tìm được nghiệm, nhưng fitA() làm tròn AxG/BxG còn 1 chữ số trước khi dùng lại nên kết quả hiển thị/quote không còn khớp target đủ chặt. Cần giữ full precision trong state và chỉ format 1 chữ số ở UI.
  + Phát hiện bất thường (Bug A1): Khi fitA() chạy xong, hàm chỉ cập nhật DOM và gọi renderAll(). Hàm KHÔNG gọi refreshLiq(), dẫn đến lệnh resting của MM-A trong sổ lệnh vẫn giữ nguyên giá cũ (0.39 / 0.44) cho đến khi chuyển sang tick kế tiếp!

---

3. CHI TIẾT THAM SỐ & ĐO LƯỜNG MODEL B - NORMAL GOAL-DIFFERENCE MODEL

3.1. Cấu hình tham số mặc định
- CONFIG.MODELS.B.BASE_MARGIN = 0.02 (Biên an toàn cơ sở 2%).
- CONFIG.MODELS.B.VAR_SCALE = 0.015 (Hệ số nhạy cảm phương sai).
- CONFIG.MODELS.B.CLAMP_MIN = 0.01, CLAMP_MAX = 0.99.
- Input UI: mu = 0.7, vari (sigma^2) = 1.5.

3.2. Đo lường cơ chế Margin Động
- Công thức: margin = 0.02 + 0.015 * sigma^2.
  + Với sigma^2 = 1.5 -> margin = 0.02 + 0.015 * 1.5 = 0.0425 (4.25%).
  + Với sigma^2 = 2.5 -> margin = 0.02 + 0.015 * 2.5 = 0.0575 (5.75%).
- Phân tích rủi ro: Khi độ phân tán trận đấu tăng, margin tự động mở rộng giúp hạn chế adverse selection.
- Lưu ý: Ý tưởng mở rộng spread đúng hướng, nhưng mapping bid/ask hiện bị đảo như mục 3.3.1 nên chưa tạo được spread bảo vệ trên CLOB.

3.3. Đo lường định giá kèo đơn vs kèo Quarter
- Kèo đơn (H = 0.0, homeLine = 0.0):
  + mu = 0.7, sigma = sqrt(1.5) xấp xỉ 1.2247.
  + z = (0 - 0.7) / 1.2247 xấp xỉ -0.5715 -> p = 1 - Phi(-0.5715) = Phi(0.5715) = 0.7162.
- Kèo Quarter (H = 0.75, homeLine = -0.75):
  + l1 = -0.75 - 0.25 = -1.00 -> -l1 = 1.00.
  + l2 = -0.75 + 0.25 = -0.50 -> -l2 = 0.50.
  + p1 = 1 - Phi((1.00 - 0.7) / sqrt(1.5)) = 1 - Phi(0.2449) xấp xỉ 0.4032.
  + p2 = 1 - Phi((0.50 - 0.7) / sqrt(1.5)) = 1 - Phi(-0.1633) = Phi(0.1633) xấp xỉ 0.5649.
  + p = 0.5 * (0.4032 + 0.5649) = 0.4841.
  + O_fair = 1 / 0.4841 = 2.066.
  + P_bid = min(0.4841 * (1 + 0.0425), 0.99) = 0.5047 -> Lay 1.981.
  + P_ask = max(0.4841 * (1 - 0.0425), 0.01) = 0.4635 -> Back 2.157.

3.3.1. Bug B0 - Đảo chiều Bid/Ask (Critical)
- Kết quả ngay trên cho thấy Bid 0.5047 > Ask 0.4635.
- Nguyên nhân trong modelB:
  + bidP được gán p * (1 + margin).
  + askP được gán p * (1 - margin).
- Khi postMMQuotes sử dụng bidP cho BUY và askP cho SELL, Model B tự tạo crossed book bất cứ khi nào margin > 0.
- Công thức cần bảo đảm bidP < p < askP, sau đó mới clamp/round theo tick size.
- Kết luận: Không được bật Model B trong MVB trước khi sửa lỗi này và thêm invariant test `bidP < askP` cho mọi miền tham số hợp lệ.

3.3.2. Giới hạn của Normal approximation
- Phân phối chuẩn liên tục gán xác suất bằng 0 cho đúng một hiệu số bàn thắng nguyên, trong khi bóng đá có point mass đáng kể tại các hiệu số đó.
- Vì vậy push ở line nguyên và payout phân đoạn AH chỉ được xấp xỉ. Muốn pricing exact theo goal distribution cần discrete goal-difference/Skellam hoặc mô hình có probability mass tại các mốc settlement.

3.4. Kiểm thử thuật toán fitB() (Binary Search)
- Kết quả thực thi trên Playwright:
  + Mục tiêu: Tìm mu trong đoạn [-1, 3] để p_modelB = p_fair = 0.4894.
  + mu tìm được: 0.72.
  + Phát hiện bất thường (Bug B1): Tương tự fitA, fitB không gọi refreshLiq(), lệnh MM-B trong sổ lệnh không phản ánh ngay mu mới.

---

4. CHI TIẾT THAM SỐ & ĐO LƯỜNG MODEL C - INVENTORY SKEW (A-S-INSPIRED)

4.1. Cấu hình tham số mặc định
- CONFIG.MODELS.C.SKEW_SCALE = 0.08 (sigma^2 = 0.08 - độ biến động).
- CONFIG.MODELS.C.BASE_HS = 0.02 (Half-spread cơ sở 2%).
- CONFIG.MODELS.C.GAMMA_SCALE = 0.1 (Hệ số phạt rủi ro theo gamma).
- CONFIG.MODELS.C.CLAMP_MIN = 0.02, CLAMP_MAX = 0.98.
- Phân loại: Đây là heuristic reservation-price skew lấy cảm hứng từ Avellaneda-Stoikov, chưa phải implementation đầy đủ vì chưa có time horizon, volatility động và order-arrival intensity trong công thức spread.

4.2. Đo lường định giá theo mức tồn kho q
- Công thức giá đặt chỗ (Reservation Price):
  r = clamp(p_fair - q * gamma * 0.08, 0.02, 0.98)
- Công thức nửa khoảng chênh lệch (Half-spread):
  hs = 0.02 + gamma * 0.1
- Thực nghiệm các mức tồn kho:
  + Mức 1: q = 0, gamma = 0.05, Fair p = 0.489
    - Reservation Price r = 0.489, Half-spread hs = 0.025.
    - Bid Price = 0.464, Ask Price = 0.514.
    - Nhận xét: Vị thế trung hòa, spread đối xứng 5%.
  + Mức 2: q = +40 (ôm nhiều YES), gamma = 0.05, Fair p = 0.489
    - Reservation Price r = 0.329, Half-spread hs = 0.025.
    - Bid Price = 0.304, Ask Price = 0.354.
    - Nhận xét: Dìm giá để kích thích thị trường BUY của đối tác.
  + Mức 3: q = -40 (short nhiều YES), gamma = 0.05, Fair p = 0.489
    - Reservation Price r = 0.649, Half-spread hs = 0.025.
    - Bid Price = 0.624, Ask Price = 0.674.
    - Nhận xét: Đẩy giá lên để kích thích thị trường SELL cho mình.

4.3. Kiểm thử khớp lệnh Market Buy/Sell & Tính Slippage
- Thực thi bấm buyBtn (User mua 20 YES):
  + Lệnh gửi: submitClob("YES", "BUY", 0.5, 20, "MARKET", "USER").
  + Khớp thành công: Qty = 20, Price = 0.470.
  + Slippage ghi nhận: 0.000 (do size 20 vừa đủ ăn hết tầng L1).
  + Tồn kho MM-C cập nhật: q -> -20 (MM-C bán ra nên short 20).
  + Vị thế User cập nhật: pos.YES = 20.
- Thực thi bấm sellBtn (User bán 20 YES):
  + Lệnh gửi: submitClob("YES", "SELL", 0.5, 20, "MARKET", "USER").
  + Khớp thành công: Qty = 20, Price = 0.510.
  + Slippage ghi nhận: 0.000.
  + Tồn kho MM-C cập nhật: q -> 0.
  + Vị thế User: pos.YES = 0.

4.4. Bug C1 - Inventory dùng để Quote không lấy từ Fill Ledger (Critical)
- modelC/mmQuotes đọc q từ S.inv.
- S.inv chỉ được thay đổi trong thao tác cTrade() của panel manual C.
- submitClob() ghi fill của MM-C vào S.pnl nhưng không cập nhật S.inv từ các fill do bots, USER order panel hoặc flow khác tạo ra.
- Hệ quả: Biểu đồ/PnL có thể cho thấy inventory MM-C thay đổi nhưng reservation price dùng để quote vẫn dựa trên q cũ.
- Cách sửa: Dùng một Position/Inventory Ledger duy nhất được cập nhật idempotent từ mọi FillEvent; Model C chỉ đọc position từ ledger đó và cancel/replace quote ngay sau fill.

4.5. Giới hạn của kết quả Slippage
- Slippage 0.000 trong case size 20 chỉ chứng minh toàn bộ lệnh khớp ở một mức giá L1.
- Cần test thêm size vượt L1, multi-level sweep, partial fill, queue position, book thay đổi trong thời gian gửi lệnh và adverse selection sau fill.

---

5. CHI TIẾT THAM SỐ & ĐO LƯỜNG MODEL D - CLOB MULTI-LEVEL LADDER & DUAL ORDERBOOK

5.1. Cấu hình tham số mặc định
- CONFIG.MODELS.D.DEF_DELTA = 0.02 (Khoảng cách giữa các tầng spread).
- CONFIG.MODELS.D.DEF_LEVELS = 3 (Số tầng báo giá: L1, L2, L3).
- CONFIG.MODELS.D.DEF_SIZE = 40 (Size mỗi tầng).
- CONFIG.MODELS.D.DEF_GAMMA = 0.04.

5.2. Đo lường cấu trúc báo giá 4 phía (Ladder Quoting)
- Tại tick fair f = 0.489, q_D = 0, delta = 0.02, Levels = 3:
  + Sổ YES:
    - Bids: Tầng L1 = 0.47, Tầng L2 = 0.45, Tầng L3 = 0.43 (Mỗi tầng size 40).
    - Asks: Tầng L1 = 0.51, Tầng L2 = 0.53, Tầng L3 = 0.55 (Mỗi tầng size 40).
  + Sổ NO (Đối ứng nhị phân 1 - p):
    - Bids: Tầng L1 = 0.49, Tầng L2 = 0.47, Tầng L3 = 0.45.
    - Asks: Tầng L1 = 0.53, Tầng L2 = 0.55, Tầng L3 = 0.57.
  + Bảo toàn bất biến:
    b_Y(k) + a_N(k) = 1.00 và a_Y(k) + b_N(k) = 1.00 cho mọi tầng k thuộc {1, 2, 3}.
    -> PASS cho các quote do riêng Model D tạo ra. Không suy ra toàn bộ best book luôn không lệch 1.00 khi có quote từ model/user khác.

5.2.1. Điều kiện còn thiếu trước Backend
- Model D hiện là quote construction, chưa gồm balance/token reservation, tick/lot validation, post-only, order acknowledgement, cancel/replace race và stale quote timeout.
- Ghost order là thanh khoản implied/derived; khi lên Backend phải có một nguồn thanh khoản canonical để tránh hiển thị hoặc khớp trùng cùng một resting order.

5.3. Kiểm thử đặt lệnh thủ công & Hủy lệnh qua UI
- Đặt lệnh Limit: BUY 15 YES @ $0.42.
  + Trạng thái sổ YES bids: Tăng từ 7 lên 8 lệnh.
  + Mã lệnh phát sinh: ID 45.
  + Dropdown hủy lệnh (cancelSel): Hiển thị chính xác text "ID 45 BUY 15/15 YES @ $0.42".
- Bấm nút "Hủy" (cancelBtn):
  + Lệnh ID 45 bị loại bỏ khỏi sổ lệnh.
  + Sổ lệnh trở về 7 lệnh.
  + Kết quả kiểm chuẩn: PASS.

---

6. CHI TIẾT THAM SỐ & ĐO LƯỜNG MODEL M - MERGE ARBITRAGE DESK (CTF-STYLE)

6.1. Quản trị Vốn & Khởi tạo Auto-Split 50/50
- Tham số cấu hình:
  + DEF_INIT_CASH = 2000 (Cho phép user đổi từ 100 đến 50.000).
  + DEF_DELTA = 0.02, DEF_EPS = 0.01, DEF_QMAX = 400, DEF_FEE = 0.003.
- Thực nghiệm đổi vốn lên 5000 qua UI Playwright:
  + Input mInitCash set = 5000.
  + Tiền mặt: cash = 2500 pUSD.
  + Cặp token hoàn chỉnh: Y = 2500, N = 2500.
  + Badge mSplitBadge: Cập nhật lập tức "Split: 2500 cash + 2500 Y/N".
  + Trạng thái Equity ban đầu: 0.0 u (Không có rủi ro định giá tại t=0).
  + Lưu ý: Chia 50/50 là policy khởi tạo vốn của simulation, không phải một yêu cầu bắt buộc của CTF/Polymarket.

6.2. Đối chiếu 6 bước vận hành được mô tả cho mỗi Tick
1. Bước 1 - Self-Cross Protection:
   + Điều kiện kích hoạt: b_Y >= a_Y hoặc b_N >= a_N.
   + Hành động: Hủy toàn bộ lệnh MM-M (dropOwner("MM-M")) và ghi log cảnh báo.
2. Bước 2 - Clean Merge Arbitrage:
   + Điều kiện: a_Y + a_N < 1 - eps - 2 * fee.
   + Khối lượng Q = min(sz_Y, sz_N, floor(cash / (sumA + 2 * fee)), 50).
   + Hành động: Mua đồng thời cả 2 cửa, sau đó gọi recycleDeskTokens(d, filled) để gộp thành tiền mặt.
   + Lợi nhuận khóa cứng: Pi_arb = M * (1 - sumA) - M * 2 * fee.
3. Bước 3 - Cân kho kết hợp Arbitrage:
   + Khi độ lệch q = Y - N > 30: Mua thêm NO nếu a_N < 0.62 để merge ra cash.
   + Khi q < -30: Mua thêm YES nếu a_Y < 0.62 để merge ra cash.
4. Bước 4 - Trải Lệnh Tạo Lập Thị Trường 4 Chiều (4-Sided Quoting):
   + Đặt 4 lệnh LIMIT size 50 tại b_Y, a_Y, b_N, a_N bảo đảm tổng đối ứng bằng 1.00.
5. Bước 5 - Tái chế Token Hoàn chỉnh (Recycling):
   + Khi min(Y, N) > 80: Rút take = min(min(Y,N) - 50, 60) cặp ra khỏi kho đổi thành cash.
6. Bước 6 - Cắt lệch vị thế khẩn cấp:
   + Khi |q| > Q_max = 400: Bắn lệnh MARKET (Fill-And-Kill) xả bớt phía dư thừa.

6.3. Các giới hạn execution/risk của Model M
- Code runMergeDesk thực tế có các bước safety, arb, flatten, recycle và cut; bước quote 4 chiều nằm trong postMergeQuotes() được gọi khi refreshLiq(), không nằm giữa flatten và recycle như mô tả 6 bước.
- Trình tự tick hiện là refresh quote -> botsAct -> runMergeDesk. Vì vậy bots/arb có thể đổi inventory sau khi quote đã được post và quote chỉ phản ánh q mới ở tick kế tiếp.
- Hai chân BUY YES và BUY NO của clean merge arb được submit tuần tự, không atomic. Nếu chân đầu fill đủ nhưng chân sau partial/fail thì desk giữ directional exposure.
- Q được tính theo size tại best direct ask, trong khi submitClob có thể chọn cả direct và implied liquidity; cần preflight trên effective book và tính PnL theo giá fill thực tế từng leg.
- Không có reserved balance cho open BUY và reserved token cho open SELL; simulation có thể cho cash/token âm trong khi Backend thật phải reject lệnh thiếu tài sản.
- Fee đang mô phỏng cố định theo share, chưa gồm fee schedule thật, gas, settlement failure/retry và latency.
- Kết luận: PASS cho nguyên lý split/merge và các branch prototype; chưa đủ cơ sở kết luận bot không bao giờ cạn cash hoặc luôn giữ toàn thị trường tại tổng giá 1.00.

---

7. KIỂM THỬ ENGINE KHỚP LỆNH CLOB & IMPLIED MATCHING (GHOST ASKS)

7.1. Logic Khớp Implied xuyên sổ (Cross-Book Matching)
- Định lý: Người mua YES tại giá p tương đương người bán NO tại giá 1 - p.
  + Khi có lệnh Bid NO tại giá b_N, hệ thống tổng hợp thành Ghost Ask YES tại giá 1 - b_N.
  + Khi có lệnh Bid YES tại giá b_Y, hệ thống tổng hợp thành Ghost Ask NO tại giá 1 - b_Y.
- Đo lường Playwright:
  + Sổ NO có Bid L1: 0.49 -> Sổ YES hiển thị Ghost Ask @ 0.51 (viền nét đứt tag-ghost).
  + Sổ YES có Bid L1: 0.47 -> Sổ NO hiển thị Ghost Ask @ 0.53.
  + Ưu tiên khớp: Engine so sánh giữa Direct Ask và Implied Ghost Ask, luôn chọn giá tốt nhất (nhỏ nhất cho BUY, lớn nhất cho SELL).

7.2. Tự triệt tiêu giao dịch nội bộ (Self-Trade Prevention)
- Kiểm tra mã nguồn submitClob:
  if (r.owner === owner) continue;
- Kết quả test: Khi MM-M hoặc USER bắn lệnh, hệ thống bỏ qua toàn bộ lệnh resting của chính chủ thể đó, loại bỏ triệt để rủi ro wash trading hoặc tự cắn lệnh. PASS.

7.3. Giới hạn của đường Post Quote hiện tại
- submitClob có matching và STP, nhưng postMMQuotes/postClobQuotes/postMergeQuotes lại push lệnh trực tiếp vào mảng book.
- Vì vậy test engine submitClob PASS không bảo đảm quote do các MM post sẽ đi qua cùng invariant matching.
- Yêu cầu Backend: mọi OrderIntent phải qua một Coordinator/Risk/Reconciler và một order-entry path duy nhất. Lệnh marketable của owner khác phải match; lệnh post-only crossing phải reject; quote của cùng owner phải được net/cancel-replace thay vì tự trade.

---

8. ĐO LƯỜNG REPLAY DÒNG THỜI GIAN TRÊN 3 TRẬN THỰC TẾ

Ghi chú phạm vi: Bộ dữ liệu có 90 trận, nhưng artifact báo cáo này chỉ cung cấp bảng replay chi tiết cho 3 trận dưới đây. Do đó không dùng ba bảng này để kết luận đã backtest/assert đủ 90 trận.

8.1. Trận 1: round20_match_2591088.csv (Bournemouth vs Everton)
- Thông số: FT 1-0, Line H từ 0.75 -> 0.75, 1309 ticks gốc, 119 ticks timeline replay.
- Kịch bản: Kèo chấp 0.75 trái, tỉ số 1-0 -> diff = 1 - 0.75 = +0.25 -> Half-Win (Thắng nửa tiền).
- Thống kê PnL kết phiên (Playwright Replay full 119 ticks):
  + BOTS: 1.597 Fills, Vol 7.942, Net YES +231, Net NO -335, Cash +262.1 u, MTM +170.4 u, Settled +351.6 u.
  + MM-A: 50 Fills, Vol 339, Net YES +91, Net NO 0, Cash -42.2 u, MTM -3.0 u, Settled +26.1 u.
  + MM-B: 1.287 Fills, Vol 6.293, Net YES -697, Net NO 0, Cash +207.9 u, MTM -91.8 u, Settled -314.8 u.
  + MM-C: 23 Fills, Vol 110, Net YES -10, Net NO 0, Cash +6.6 u, MTM +2.3 u, Settled -0.9 u.
  + MM-D: 118 Fills, Vol 595, Net YES +11, Net NO -38, Cash -16.8 u, MTM -33.7 u, Settled -18.0 u.
  + MM-M: 121 Fills, Vol 645, Net YES 0, Net NO -1, Cash -44.4 u, MTM -44.9 u, Settled -44.6 u.
  + USER: 2 Fills, Vol 40, Net YES 0, Net NO 0, Cash +0.8 u, MTM +0.8 u, Settled +0.8 u.
  + TỔNG: 3.198 Fills, Vol 15.964, Net YES -374, Net NO -374, Cash +374.0 u, MTM -44.3 u, Settled -44.0 u.

8.2. Trận 2: round20_match_2591089.csv (Cửa trên chấp sâu thua kèo)
- Thông số: FT 2-1, Line H từ 1.5 -> 1.75, 1150 ticks gốc.
- Kịch bản: Cửa trên chấp 1.75 trái, thắng 2-1 -> diff = 1 - 1.75 = -0.75 -> Full-Loss (Thua cả tiền).
- Thống kê PnL kết phiên:
  + BOTS: 1.714 Fills, Vol 8.524, Net YES +1.345, Net NO -1.285, Cash +1.178.8 u, MTM +419.8 u, Settled -106.2 u.
  + MM-A: 144 Fills, Vol 717, Net YES -707, Net NO 0, Cash +290.1 u, MTM +148.7 u, Settled +290.1 u.
  + MM-B: 1.010 Fills, Vol 4.772, Net YES -4.772, Net NO 0, Cash +1.188.8 u, MTM +234.4 u, Settled +1.188.8 u.
  + MM-C: 516 Fills, Vol 2.813, Net YES +2.813, Net NO 0, Cash -1.348.4 u, MTM -785.8 u, Settled -1.348.4 u.
  + MM-D: 18 Fills, Vol 85, Net YES +19, Net NO 0, Cash -11.2 u, MTM -7.4 u, Settled -11.2 u.
  + MM-M: 26 Fills, Vol 137, Net YES +17, Net NO 0, Cash -13.2 u, MTM -9.8 u, Settled -13.2 u.

8.3. Trận 3: round20_match_2591090.csv (Cửa dưới hòa bóng ăn trọn)
- Thông số: FT 1-1, Line H từ -0.5 -> -0.75, 1544 ticks gốc.
- Kịch bản: Cửa chủ nhà được chấp +0.75, tỉ số 1-1 -> diff = 0 + 0.75 = +0.75 -> Full-Win (Thắng trọn).
- Thống kê PnL kết phiên:
  + BOTS: 1.984 Fills, Vol 10.283, Net YES -1.636, Net NO +1.611, Cash +2.434.1 u, MTM +2.356.7 u, Settled +798.1 u.
  + MM-A: 303 Fills, Vol 1.478, Net YES +1.478, Net NO 0, Cash -1.197.2 u, MTM -428.6 u, Settled +280.8 u.
  + MM-B: 1.039 Fills, Vol 5.130, Net YES +5.118, Net NO 0, Cash -4.601.2 u, MTM -1.939.9 u, Settled +516.8 u.
  + MM-C: 558 Fills, Vol 3.218, Net YES -3.218, Net NO 0, Cash +1.684.6 u, MTM +11.2 u, Settled -1.533.4 u.
  + MM-D: 37 Fills, Vol 192, Net YES -84, Net NO 0, Cash +53.8 u, MTM +10.1 u, Settled -30.2 u.
  + MM-M: 47 Fills, Vol 265, Net YES -50, Net NO -3, Cash +17.9 u, MTM -9.6 u, Settled -32.1 u.

---

9. TỔNG HỢP CÁC LỖI PHÁT HIỆN (BUGS & ANOMALIES LOG)

9.1. Lỗi 1 [Nghiêm trọng]: Sổ lệnh bị Chéo giá (Crossed Orderbook: Best Bid > Best Ask)
- Vị trí: Hàm postMMQuotes() kết hợp với việc bật đồng thời Model A và Model D/C/M.
- Nguyên nhân:
  + Model A khi chưa bấm "Fit A" dùng tham số mặc định (AxG = 1.8, BxG = 1.1), tự tính ra giá bán Ask YES = 0.44.
  + Trong khi đó, Model D/C neo theo giá fair thị trường (0.489), đặt Bid YES = 0.47.
  + Lệnh của các MM được push trực tiếp vào mảng S.book.YES.bids và S.book.YES.asks mà không đi qua cơ chế khớp lệnh tự động.
  + Kết quả: Best Bid (0.47) > Best Ask (0.44). Sổ lệnh rơi vào trạng thái chéo giá.
- Hệ quả dây chuyền:
  + Khi sổ lệnh bị chéo, Bước 1 của Model M (runMergeDesk) phát hiện b_Y >= a_Y, lập tức kích hoạt cơ chế tự vệ dropOwner("MM-M"). Khiến cho toàn bộ báo giá và hoạt động arbitrage của Model M bị tê liệt hoàn toàn khi bật song song Model A chưa fit!
- Giải pháp khắc phục:
  1. Khi khởi tạo trận đấu, tự động chạy fitA() để đồng bộ AxG, BxG khớp với fair thị trường trước khi post lệnh.
  2. Hoặc trong hàm postMMQuotes(), trước khi đưa lệnh vào sổ, nếu phát hiện lệnh mới cross với lệnh resting của MM khác thì phải cho khớp triệt tiêu trước (clean crossing) thay vì để tồn tại song song trong sổ.

9.2. Lỗi 2 [Giao diện/Logic]: Nút "Fit A" và "Fit B" không làm mới Sổ lệnh (Stale Book Quotes)
- Vị trí: Hàm fitA() và fitB().
- Nguyên nhân:
  + Cả hai hàm sau khi tính toán nghiệm bisection chỉ cập nhật giá trị vào các ô input HTML (axg, bxg, mu) và gọi renderAll().
  + Không hề có lệnh refreshLiq(fairAt(S.idx)) được gọi.
- Hệ quả:
  + Người dùng bấm Fit, thấy số liệu trên UI thay đổi nhưng sổ lệnh và đồ thị Depth vẫn hiển thị các lệnh cũ cho đến khi người dùng bấm tiến tick (step).
- Giải pháp khắc phục:
  + Thêm dòng if (S.peg) refreshLiq(fairAt(S.idx)); vào cuối hàm fitA() và fitB() trước khi gọi renderAll().

9.3. Lỗi 3 [Critical]: Model B tự tạo Crossed Spread
- Vị trí: modelB() và postMMQuotes().
- Hiện tượng: Với p = 0.4841, variance = 1.5, margin = 0.0425, code trả Bid = 0.5047 và Ask = 0.4635.
- Nguyên nhân: bidP dùng p * (1 + margin), askP dùng p * (1 - margin), ngược với quan hệ bid < fair < ask.
- Hệ quả: Bật Model B có thể làm book crossed ngay cả khi không có Model A/C/D xung đột và tiếp tục kích hoạt safety của Model M.
- Giải pháp: Sửa mapping bid/ask; thêm property test trên toàn miền config để assert 0 < bidP < mid < askP < 1 sau tick rounding.

9.4. Lỗi 4 [Critical]: Model C không đồng bộ Inventory từ Fill Engine
- Vị trí: modelC()/mmQuotes(), cTrade() và submitClob().
- Hiện tượng: q thay đổi khi dùng nút Market Buy/Sell của panel C, nhưng không đổi khi MM-C fill với bots hoặc order flow khác.
- Nguyên nhân: Quote đọc S.inv; fill engine chỉ cập nhật S.pnl.
- Hệ quả: Reservation price và spread không phản ánh exposure thật, làm mất tác dụng inventory skew trong replay chính.
- Giải pháp: Dùng Position Ledger duy nhất cập nhật từ mọi FillEvent và kích hoạt owner-specific cancel/replace sau fill.

9.5. Lỗi 5 [Critical/Specification]: Settlement AH không thống nhất
- Vị trí: payoutYES() trong simulation so với resolveAHHomeCover() của module AH-MVP.
- Hiện tượng: Simulation payout half-win = 0.75, half-loss = 0.25; module AH-MVP phân loại tương ứng thành Yes và No, push thành Void.
- Hệ quả: Fair Model A/B, settled PnL và contract resolution có thể dùng ba semantics khác nhau.
- Giải pháp: Viết market-resolution specification chính thức và contract tests dùng chung fixture cho simulation, Backend và smart contract.

9.6. Lỗi 6 [High]: Model M có Leg Risk và Quote Stale sau Fill
- Vị trí: runMergeDesk(), postMergeQuotes(), step().
- Hiện tượng: Hai chân arb gửi tuần tự; quote M được post trước botsAct/runMergeDesk và không được rebuild ngay sau khi Y/N đổi.
- Hệ quả: Partial fill một chân tạo exposure; quote sau fill có thể dùng inventory cũ đến tick kế tiếp.
- Giải pháp: Preflight effective depth, ưu tiên FOK/atomic batch nếu hạ tầng hỗ trợ, hedge/rollback khi leg thứ hai fail, và requote từ inventory ledger sau mỗi confirmed fill.

9.7. Lỗi 7 [Medium]: Các đường UI khác cũng có thể tạo Stale Quote
- Đổi gamma/inventory C và scrub/to-close timeline hiện chủ yếu gọi renderAll(), không bảo đảm refresh/cancel-replace quote.
- Giải pháp: Tách render UI khỏi quote lifecycle; mọi thay đổi input/state ảnh hưởng pricing phải phát QuoteInvalidated event cho Reconciler.

9.8. Lỗi 8 [Biên an toàn]: Thứ tự truyền tham số hàm pois(l, k)
- Vị trí: Hàm pois(l, k) đặt l (lambda) trước, k sau.
- Khuyến nghị: Cần thêm Type annotation (JSDoc hoặc TypeScript) rõ ràng `/** @param {number} lambda @param {number} k */` để tránh nhầm lẫn khi port mã nguồn sang Backend plugin.

---
Ghi chú: Toàn bộ thông số đo lường trên được thực hiện qua kịch bản kiểm thử tự động trên giao diện simulation cục bộ.

Giới hạn QA: Playwright xác nhận tốt UI/E2E, nhưng chưa thay thế Unit/Property Test, deterministic engine replay, risk/solvency test, concurrency/latency/chaos test và backtest calibration/PnL sau fee. Trước MVB cần bổ sung các lớp test này và chạy report tổng hợp đủ 90 trận với cùng một cấu hình/version cố định.
