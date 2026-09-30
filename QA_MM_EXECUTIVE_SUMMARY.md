BÁO CÁO TỔNG HỢP & GÓP Ý 5 THUẬT TOÁN MM GỬI ANH DUY

Gửi anh Duy,

Em vừa chạy automation test các luồng chính của 5 thuật toán Market Maker (MM) và sổ lệnh CLOB trong file simulation HTML trên bộ dữ liệu chứa 90 trận mẫu. Các hàm toán nền như de-vig, Poisson, ncdf và settleMult cho kết quả đúng ở các test case đã kiểm tra. Tuy nhiên, em chưa đánh giá bản hiện tại là sẵn sàng ráp thẳng vào Backend vì còn một số lỗi về bid/ask, đồng bộ inventory, settlement AH và execution hai chân của merge arbitrage.

Dưới đây em tổng hợp lại kết quả kiểm tra từng thuật toán, 2 lỗi ban đầu bắt được qua Playwright, các blocker bổ sung khi đối chiếu code và hướng đề xuất để chuẩn bị ráp vô Backend theo đúng plan 3 tháng anh nhé.

File thông số chi tiết đo lường từng trận em để ở đây: QA_MM_DETAILED_METRICS.md
---

1. ĐÁNH GIÁ 5 THUẬT TOÁN MM VÀ KHẢ NĂNG RÁP BACKEND

1.1. Model A (Poisson xG)
+ Đánh giá của em: Phần phân phối Poisson độc lập và ma trận tỉ số 0-0 đến 10-10 chạy đúng theo công thức đang cài đặt. Tuy nhiên cần chốt rõ contract settlement AH: Model A đang dùng fair = pWin + 0.5 * pHalfWin, trong khi phần PnL của simulation dùng payout phân đoạn 1 / 0.75 / 0.5 / 0.25 / 0. Hai cách này chưa cùng một định nghĩa giá trị kỳ vọng. Fit A cũng làm tròn AxG/BxG còn 1 chữ số nên fair sau fit có thể lệch target.
+ Khả năng lên BE: Phù hợp làm tín hiệu fair pre-match. Chi phí ma trận 11 x 11 không phải blocker lớn ở quy mô nhỏ; hạn chế chính cho in-play là model chưa có state phút thi đấu, tỉ số hiện tại, thẻ đỏ và thời gian còn lại. Khi port cần giữ nghiệm xG full precision trong state, chỉ làm tròn khi hiển thị, và xử lý/chuẩn hóa phần xác suất tail trên 10 bàn.

1.2. Model B (Normal Goal-Difference)
+ Đánh giá của em: Công thức xác suất chạy nhẹ và cách lấy trung bình hai line cho kèo quarter là một approximation hợp lý. Tuy nhiên code hiện đang gán bidP = p * (1 + margin) và askP = p * (1 - margin), làm Bid > Ask khi margin dương; ví dụ test ra Bid 0.5047 > Ask 0.4635. Đây là lỗi nghiêm trọng khiến Model B tự tạo crossed book. Ngoài ra phân phối chuẩn liên tục không có point mass tại hiệu số bàn thắng nguyên, nên xác suất push chỉ là xấp xỉ chứ không phải AH exact.
+ Khả năng lên BE: Có tiềm năng làm fair signal nhanh cho in-play, nhưng chỉ sau khi sửa chiều bid/ask, chốt semantics push/quarter payout và bổ sung state live. Chưa nên bật Model B trong MVB production ở trạng thái hiện tại.

1.3. Model C (Inventory Skew, lấy cảm hứng từ Avellaneda-Stoikov)
+ Đánh giá của em: Công thức reservation price phản ứng đúng chiều với q trong test thủ công. Tuy nhiên đây mới là heuristic A-S-inspired, chưa phải công thức Avellaneda-Stoikov đầy đủ vì chưa dùng time horizon, volatility động và order-arrival intensity để tính spread tối ưu. Quan trọng hơn, q dùng để quote hiện là S.inv và chỉ được cập nhật trong nút trade thủ công; fill từ bots/engine chỉ đi vào S.pnl nên Model C chưa phản ứng theo inventory thật của mọi fill.
+ Kết quả slippage L1 = 0.000 chỉ chứng minh lệnh size 20 không vượt thanh khoản tầng đầu trong case đó, chưa đủ kết luận execution luôn tốt.
+ Khả năng lên BE: Inventory skew là thành phần bắt buộc, nhưng phải lấy position từ fill ledger thống nhất và requote ngay sau fill trước khi đưa vào MVB.

1.4. Model D (CLOB Ladder Quoting)
+ Đánh giá của em: Báo giá đa tầng L1-L3 và các cặp quote do D tạo ra thỏa b_Y + a_N = 1 và a_Y + b_N = 1. Ghost Asks hiển thị thanh khoản implied trực quan. Đây là bất biến của quote riêng Model D, không có nghĩa toàn bộ best book luôn giữ tổng 1.00 khi còn lệnh từ model/user khác.
+ Khả năng lên BE: Phù hợp làm lớp quote construction tạo depth cho MVB, nhưng cần đứng sau một lớp risk/reconciliation chung để kiểm tra tick size, balance/token reservation, post-only, self-trade prevention và cancel/replace. Ghost liquidity chỉ nên là derived view hoặc implied matching, không được đếm trùng thanh khoản.

1.5. Model M (Merge Arbitrage Desk)
+ Đánh giá của em: Nguyên lý split một đơn vị collateral thành cặp Y/N và merge cặp trở lại collateral là đúng. Auto-split 50/50 giữ equity khởi tạo trung hòa theo công thức simulation. Tuy nhiên cách chia 50/50 là policy treasury của bot, không phải một chuẩn bắt buộc của Polymarket.
+ Hai lệnh mua YES và NO hiện được gửi tuần tự, không atomic; một chân có thể fill còn chân kia fail/partial và tạo leg risk. Quote cũng chưa reserve cash/token, nên chưa thể kết luận bot “không bao giờ cạn tiền mặt”. Model M chỉ giữ quan hệ bù trừ cho quote riêng của mình, không thể bảo đảm toàn thị trường luôn có tổng giá đúng 1.00.
+ Khả năng lên BE: Có giá trị cho treasury/recycling và arb, nhưng nên chạy replay/shadow trước. Khi lên BE cần FOK/preflight cho hai chân, xử lý partial fill, balance reservation, fee/gas thật, idempotency và reconciliation sau settlement.

---

2. CÁC VẤN ĐỀ LOGIC EM PHÁT HIỆN ĐƯỢC TRONG QUÁ TRÌNH TEST

2.1. Lỗi sổ lệnh bị chéo giá làm ngắt Model M (Nghiêm trọng nhất)
- Hiện tượng: Khi em bật song song Model A (đang để thông số xG mặc định, tự tính giá bán Ask YES = 0.44) cùng với Model D hoặc Model C (đang neo theo fair thị trường mua Bid YES = 0.47), sổ lệnh lập tức bị chéo: Bid 0.47 > Ask 0.44.
- Hậu quả: Trong hàm runMergeDesk, Bước 1 có cơ chế bảo vệ nếu b_Y >= a_Y thì gọi dropOwner("MM-M") và dừng. Vì vậy khi bật đồng thời Model A chưa Fit, Model M bị ngắt hoàn toàn, không thể quote và không thể săn arbitrage được.
- Đề xuất của em:
  + Trên giao diện HTML: Khi nạp trận hoặc bật Model A, mình nên cho tự động chạy Fit A một lần để đồng bộ xG theo fair thị trường.
  + Trên Backend thật: Khi Bot MM đẩy lệnh Maker vào, Matching Engine của BE cần cho so khớp triệt tiêu ngay các lệnh đối ứng bị chéo (Clean Crossing) trước khi lưu lệnh dư vào sổ resting, không để xảy ra tình trạng Bid > Ask cùng nằm trong sổ.

2.2. Lỗi nút Fit A và Fit B không tự cập nhật lại sổ lệnh
- Hiện tượng: Khi em bấm Fit A hoặc Fit B, hai hàm này tính xong bisection thì chỉ gán số mới vào ô input trên màn hình rồi gọi renderAll(), nhưng lại quên gọi refreshLiq(fairAt(S.idx)).
- Hậu quả: Số trên ô input đã đổi nhưng lệnh của MM-A và MM-B trong sổ lệnh và trên đồ thị Depth vẫn là lệnh cũ, phải bấm tiến sang tick sau thì sổ mới cập nhật.
- Đề xuất của em:
  + Em thấy chỉ cần thêm một dòng gọi làm mới thanh khoản trước khi render là giải quyết xong:
    if (S.peg) refreshLiq(fairAt(S.idx));

2.3. Các lỗi/blocker bổ sung phát hiện khi đối chiếu code
- Model B đảo chiều spread: bidP > askP khi margin dương, tự tạo crossed book ngay cả khi chạy riêng.
- Model C không dùng inventory từ fill ledger: q chỉ đổi qua thao tác manual C, không đổi theo fill của bots/user qua engine.
- Settlement AH chưa thống nhất: simulation dùng payout YES 1 / 0.75 / 0.5 / 0.25 / 0, còn module AH-MVP Backend đang phân loại half-win = Yes, half-loss = No, push = Void. Cần chốt contract rule trước khi tính fair/PnL.
- Model M không thực thi quote như một bước atomic trong runMergeDesk; quote được post trước bots/arb nên có thể stale sau khi inventory đổi. Hai chân arb tuần tự có partial-fill risk.
- Ngoài Fit A/B, thao tác đổi gamma/inventory C và scrub/to-close timeline cũng có thể render UI nhưng chưa cancel/replace quote tương ứng.

---

3. KẾ HOẠCH RÁP MM VÔ BACKEND DẠNG PLUGIN THEO PLAN 3 THÁNG

Theo đúng định hướng làm bản MVB trước mà anh dặn, em phác thảo cách tổ chức module bot MM để cắm vào Backend OKAS như sau:

3.1. Thiết kế Plugin Interface bằng TypeScript
Em đề xuất tạo một interface chuẩn để sau này anh em mình viết thêm model mới chỉ cần implement theo khung này:

```typescript
export interface MarketMakerPlugin {
  readonly metadata: PluginMetadata;
  init(context: PluginContext): Promise<void>;
  evaluate(context: QuoteContext): Promise<QuotePlan>;
  onEvent(event: MarketEvent | OrderEvent | FillEvent): Promise<void>;
  snapshot(): Promise<PluginState>;
  shutdown(reason: ShutdownReason): Promise<void>;
}
```

Plugin chỉ trả về desired QuotePlan; không tự gọi exchange. Một Coordinator/Risk/Reconciler chung sẽ kiểm tra sequence/timestamp, market status, tick/lot size, balance đã reserve, inventory/Qmax, post-only/FOK/FAK, self-cross, clientOrderId/idempotency rồi mới cancel/replace hoặc submit vào CLOB.

Không nên coi A/B/C/D/M là 5 plugin ngang hàng cùng tự đẩy quote. Hướng ghép phù hợp hơn:
- A/B: fair-value signal.
- C: inventory/risk adjustment.
- D: ladder/quote construction.
- M: treasury, split/merge và arbitrage riêng.
- Coordinator trung tâm: hợp nhất output, chống self-cross và quản lý order lifecycle.

3.2. Lộ trình triển khai cụ thể

- Tháng 1: Chốt contract AH, sửa Simulation & Đóng gói Core Toán học
  + Chốt một semantics duy nhất cho full-win/half-win/push/half-loss/full-loss giữa smart contract, Backend và simulation.
  + Sửa Model B crossed spread, Model C inventory ledger, Fit/stale quote và execution Model M.
  + Viết Unit/Property Test cho devig, settleMult, ncdf, pois, fair payout, bid < ask, conservation Y/N/collateral và các boundary ±0.25.
  + Tách fair signal, inventory adjustment, quote plan và execution/risk thành module riêng.

- Tháng 2: Dựng Service Bot MM nội bộ trên Backend (Mục tiêu MVB)
  + Dựng Coordinator, Risk Engine, balance reservation, idempotent order gateway, cancel/replace, reconciliation và kill switch.
  + Đưa Model D đi cùng inventory/risk Model C ngay từ đầu; không chạy ladder production khi chưa có giới hạn tồn kho.
  + Cho Model M chạy replay/shadow trước, test riêng partial fill và lỗi một chân arb.
  + Kết nối API/WebSocket nội bộ sau khi có contract rõ ràng với Matching Engine.

- Tháng 3: Canary/Testnet & Hoàn thiện sản phẩm MVB
  + Chạy Model M với limit nhỏ sau khi test atomicity/recovery; thêm A/B làm fair signal sau khi Model B được sửa và calibration đạt yêu cầu.
  + Tích hợp Dashboard theo dõi realized/unrealized PnL, cash/token available và reserved, inventory, stale quote, reject rate, latency, partial fills và kill-switch state.
  + Chạy replay đủ 90 trận, load/soak, disconnect/reconnect, event trùng/out-of-order và testnet Polygon Amoy trước canary.
  + Đóng gói Docker để chuẩn bị cho giai đoạn scale tiếp theo.

---

4. BƯỚC TIẾP THEO

+ Anh Duy xem qua các lỗi và blocker em note ở trên xem hướng xử lý như vậy đã hợp ý anh chưa nhé; nếu phần nào chưa đúng với contract/plan Backend hiện tại thì anh phản hồi để em cập nhật lại test specification.
+ Trước khi ráp Backend, mình cần thêm repo/API contract của Matching Engine vì repo OKAS hiện có trong workspace là frontend kết nối tới managed CLOB, chưa có Local Matching Engine để kiểm chứng tích hợp end-to-end.
+ Khi anh nghiên cứu xong paper và chốt contract settlement AH, anh em mình thống nhất Interface Plugin/Coordinator ở Mục 3 rồi mới ráp khung module vào Backend để tránh lặp lại crossed quote giữa các strategy.
