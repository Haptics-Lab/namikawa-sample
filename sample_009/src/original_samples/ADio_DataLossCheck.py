"""
ADio データ欠損検証プログラム

■ユーザーが変更する項目
    TARGET_SERIAL
    FS_KSPS
    CHUNK_RATE_HZ
    REQUEST_DATA_NUM
    RECORD_SECONDS
    SIGNAL_FREQ
    SIGNAL_AMP

■通常変更不要
    CHUNK_SIZE
    CHUNK_NUM

■出力ファイル
    adc_log.bin

■評価内容
    ・受信件数確認
    ・保存件数確認
    ・チャンク連続性確認
    ・波形ジャンプ確認
    ・周波数確認
"""


import time
import threading
import struct
import os
import math
import queue

from queue import Queue
from collections import defaultdict
from ADio_Utils import (
    open_ftdi,
    flush_input_buffer,
    _readline,
    read_exact,
    get_sampling_command,
    convert_to_voltage,
    list_ftdi_serials
)
import ftd2xx.defines as fd
from collections import defaultdict


logging_queue = Queue()
file_queue = Queue(maxsize=20000)
sync_ready = threading.Event()
raw_queue = Queue(maxsize=4000) 
recv_done = threading.Event()
log_done = threading.Event()

# ==========================================================
# ユーザー設定
#
# TARGET_SERIAL     : ADioのFTDIシリアル番号
# FS_KSPS           : サンプリング速度[kSPS]
# CHUNK_RATE_HZ     : チャンク取得周期[Hz]
# REQUEST_DATA_NUM  : 取得チャネル数
# RECORD_SECONDS    : 記録時間[秒]
# SIGNAL_FREQ       : 入力信号周波数[Hz]
# SIGNAL_AMP        : 入力信号振幅[V]
# ==========================================================
# ==== ユーザー設定 ====
TARGET_SERIAL = "FT9YKFGE"
FS_KSPS = 16
CHUNK_RATE_HZ = 200
REQUEST_DATA_NUM = 9
RECORD_SECONDS = 15

SIGNAL_FREQ = 500
SIGNAL_AMP = 4.5

# ==== 自動計算（通常変更不要） ====
CHUNK_SIZE = int(FS_KSPS * 1000 / CHUNK_RATE_HZ)

CHUNK_NUM = int(RECORD_SECONDS * CHUNK_RATE_HZ)

voltage_threshold = (
    2 * math.pi * SIGNAL_FREQ * SIGNAL_AMP
    * (1 / CHUNK_RATE_HZ)
    * 0.35
)


BIN_FILE = "adc_log.bin"

running = True

if CHUNK_SIZE > 2047:
    raise ValueError(f"CHUNK_SIZE={CHUNK_SIZE} は上限2047を超えています")

# ==== コマンド送信 ====
def send_command(handle, command, expect_response=True):
    handle.write(command.encode())

    if expect_response:
        line = _readline(handle, timeout=1.0)  # ← readline() を使う
        if not line:
            print("No valid response received.")
            return None

        decoded = line.decode(errors="ignore").strip()
        for res_line in decoded.splitlines():
            res_line = res_line.strip()
            if res_line.startswith("*"):
                print(f"Response: {res_line}")
                return res_line
            elif res_line:
                print(f"[WARN] Invalid response: {res_line}")

    return None


# ==== 受信 ====
receiver_ready = threading.Event()
recv_chunk_index = defaultdict(int)
logger_ready = threading.Event()

total_size = CHUNK_SIZE * 5 + 7

saved_chunk_count = defaultdict(int)

def count_cycles(signal, fs, freq, threshold=0.5):
    if not signal:
        return 0

    min_interval = int(fs / freq * 0.5)  # 半周期より短いのは無視

    count = 0
    armed = False
    last_index = -min_interval

    for i, v in enumerate(signal):
        if v < -threshold:
            armed = True

        elif armed and v >= threshold:
            if i - last_index >= min_interval:
                count += 1
                last_index = i
            armed = False

    return count

def analyze_zero_cross_intervals(signal, fs, threshold=0.5):
    """
    負→正のゼロクロス位置を抽出し、周期間隔を解析する
    fs: サンプリング周波数 [Hz]
    threshold: ヒステリシス用しきい値 [V]
    戻り値:
        cycles          : 検出周期数
        est_freq        : 推定周波数 [Hz]
        mean_interval   : 平均周期 [s]
        std_interval    : 周期標準偏差 [s]
        min_interval    : 最小周期 [s]
        max_interval    : 最大周期 [s]
        intervals       : 各周期長の配列 [s]
    """
    if len(signal) < 2:
        return 0, 0.0, 0.0, 0.0, 0.0, 0.0, []

    crossings = []
    armed = False

    for i, v in enumerate(signal):
        if v < -threshold:
            armed = True
        elif armed and v >= threshold:
            crossings.append(i)
            armed = False

    cycles = len(crossings)

    if len(crossings) < 2:
        return cycles, 0.0, 0.0, 0.0, 0.0, 0.0, []

    intervals = []
    for i in range(1, len(crossings)):
        dt = (crossings[i] - crossings[i - 1]) / fs
        intervals.append(dt)

    mean_interval = sum(intervals) / len(intervals)

    if mean_interval > 0:
        est_freq = 1.0 / mean_interval
    else:
        est_freq = 0.0

    if len(intervals) >= 2:
        var = sum((x - mean_interval) ** 2 for x in intervals) / len(intervals)
        std_interval = var ** 0.5
    else:
        std_interval = 0.0

    min_interval = min(intervals)
    max_interval = max(intervals)

    return cycles, est_freq, mean_interval, std_interval, min_interval, max_interval, intervals

def receive_data(handle):
    receiver_ready.set()
    idle_after_stop = 0

    try:
        while running or handle.getQueueStatus() > 0:
            try:
                line = read_exact(handle, total_size, timeout=0.5)
                if not line:
                    if not running:
                        idle_after_stop += 1
                        if idle_after_stop >= 3:
                            break
                    else:
                        time.sleep(0.001)
                    continue

                idle_after_stop = 0

                if line.endswith(b"\r\n"):
                    line = line[:-2]
                elif line.endswith(b"\n"):
                    line = line[:-1]

                if not (line.startswith(b"*40") and line.endswith(b"#")):
                    continue

                try:
                    ch = int(line[3:4], 16)
                except Exception:
                    continue

                payload = line[4:-1]
                if len(payload) != 5 * CHUNK_SIZE:
                    print(f"[WARN] payload size mismatch: got={len(payload)} expected={5*CHUNK_SIZE}")
                    continue

                idx = recv_chunk_index[ch]
                recv_chunk_index[ch] += 1

                try:
                    raw_queue.put((ch, idx, payload), timeout=0.2)
                except queue.Full:
                    print(f"[QUEUE FULL: raw_queue] ch{ch} idx={idx}")
                    continue

            except Exception as e:
                print(f"受信終了（ポートクローズ？）: {e}")
                break
    finally:
        recv_done.set()



# === writer_thread(ファイル保存) ===
def writer_thread():
    flush_interval = 200
    counter = 0
    with open(BIN_FILE, "wb") as f:
        while not log_done.is_set() or not file_queue.empty():
            try:
                ch, index, values = file_queue.get(timeout=0.5)
                packed = struct.pack(f"<B H {CHUNK_SIZE}f", ch, index, *values)
                f.write(packed)
                saved_chunk_count[ch] += 1
                counter += 1
                if counter % flush_interval == 0:
                    f.flush()
            except queue.Empty:
                continue
        f.flush()
        os.fsync(f.fileno())

def logging_loop():
    """
    変換スレッド：raw_queue から取り出し、HEX→int→V をここで行う。
    変換後に file_queue（writer 用）と“観測用の内部処理”へ流す。
    """
    global running
    logger_ready.set()


    # ΔV検出用の最後の値（必要なら使用）
    prev_last_value = defaultdict(lambda: None)

    print("[LOG] logging_loop started (converter thread)")

    # 速度微調整のため関数参照をローカルにキャッシュ
    to_int_hex = int
    to_volt = convert_to_voltage

    while not recv_done.is_set() or not raw_queue.empty():
        try:
            ch, idx, payload = raw_queue.get(timeout=0.2)
        except queue.Empty:
            continue

        # bytes→ascii（エラーは握りつぶして“不正”扱い）
        try:
            s = payload.decode('ascii', 'ignore')
        except Exception:
            print(f"[WARN] ascii decode failed: ch{ch} idx={idx}")
            continue

        # 5桁HEXごとにパース
        # ★ 高速化ポイント：局所変数に束縛、for ループ内でスライス
        try:
            values = [0.0] * CHUNK_SIZE
            base = 0
            for i in range(CHUNK_SIZE):
                adc = to_int_hex(s[base:base+5], 16)  # 5桁HEX → int
                values[i] = to_volt(adc)              # int → V
                base += 5
        except Exception as e:
            print(f"[WARN] parse/convert failed: ch{ch} idx={idx} err={e}")
            continue

        # ここで“観測用処理（任意）”：ΔV検出など
        last = values[-1]
        prv = prev_last_value[ch]
        if prv is not None:
            diff = abs(values[0] - prv)
            if diff > voltage_threshold:
                print(f"⚠️ [WARN] waveform jump detected CH{ch} ΔV={diff:.4f}V > {voltage_threshold:.4f}V (idx={idx})")
        prev_last_value[ch] = last

        # writer へ受け渡し（従来の形式と同じ：float32）
        try:
            file_queue.put((ch, idx, values), timeout=0.5)
        except queue.Full:
            print(f"[QUEUE FULL: file_queue] ch{ch} idx={idx}")
            # 保存が追いついていない。flush間隔やディスクI/Oを見直す
            continue
    log_done.set()



def send_data_request_loop(handle, cmds, first_interval, repeat_interval):
    print("データ要求送信中...(最初: {}秒、その後: {}秒ごと)".format(first_interval, repeat_interval))

    # 最初の送信はmain()で済ませている前提
    interval = first_interval

    while running:
        time.sleep(interval)
        if not running or handle is None:
            break  # ★ 終了＆無効ハンドルチェック

        try:
            handle.write(cmds.encode())
        except Exception as e:
            print(f"[SEND] 書き込み中にエラーが発生しました: {e}")
            return

        # 2回目以降はrepeat_intervalで固定
        interval = repeat_interval


# ==== メイン ====
def main():
    global running
    global sync_ready

    # 自動終了時の余裕時間
    # ADio側には CHUNK_NUM 分の送信要求を出しているため、
    # RECORD_SECONDS ぴったりではなく、少し余裕を見て停止処理に入る
    AUTO_STOP_MARGIN_SEC = 0.5

    # ==== 計測条件ログ ====
    print("\n===== 計測条件 =====")
    print(f"変換速度 (FS_KSPS):     {FS_KSPS} kSPS")
    print(f"チャンク周期 (CHUNK_RATE_HZ): {CHUNK_RATE_HZ} Hz")
    print(f"チャンクサイズ (CHUNK_SIZE):  {CHUNK_SIZE} samples")
    print(f"チャネル数 (REQUEST_DATA_NUM): {REQUEST_DATA_NUM}")
    print(f"波形周波数 (SIGNAL_FREQ):     {SIGNAL_FREQ} Hz")
    print(f"波形振幅 (SIGNAL_AMP):        ±{SIGNAL_AMP} V")
    print(f"記録時間 (RECORD_SECONDS):   {RECORD_SECONDS} 秒")
    print(f"自動停止余裕時間:            {AUTO_STOP_MARGIN_SEC} 秒")
    print(f"ΔVしきい値:                {voltage_threshold:.6f} V")
    print("=====================\n")

    # ==== FTDIデバイスを開く ====
    FTlist = list_ftdi_serials()
    print(FTlist)
    handle = open_ftdi(TARGET_SERIAL)
    if handle is None:
        print("[ERROR] FTDIデバイスの初期化に失敗")
        return

    try:
        # ==== ADio 初期化 ====
        handle.purge(fd.PURGE_RX | fd.PURGE_TX)
        command = "*F0000000#"  # reset
        print(f"command:{command}")
        handle.write(command.encode())
        time.sleep(1)
        response = flush_input_buffer(handle)

        for ch in range(REQUEST_DATA_NUM):
            command = f"*10{ch:X}0{CHUNK_SIZE:04X}#"
            print(command)
            send_command(handle, command)

        cmd = get_sampling_command(FS_KSPS, 0)
        print(f"[DEBUG] サンプリング設定コマンド(CH1~8)送信: {cmd}")
        send_command(handle, cmd)

        if FS_KSPS != 256:
            cmd = get_sampling_command(FS_KSPS, 1)
            print(f"[DEBUG] サンプリング設定コマンド(CH9~16)送信: {cmd}")
            send_command(handle, cmd)

        command = "*40020000#"
        print(command)
        send_command(handle, command)

        # --- 事前に全CHぶんの送信コマンドを作成 ---
        cmds = ''.join(
            f"*40{ch:X}1{CHUNK_NUM - 1:04X}#"
            for ch in range(REQUEST_DATA_NUM)
        )
        print("一括送信コマンド:", cmds)

        # --- ダミー送信（CH0のプレトリガ） ---
        command = "*40010001#"
        print("CH0の1チャンク同期受信を待機中...")
        handle.write(command.encode())

        response = flush_input_buffer(handle)

        # ==== writer_thread は単独で先に起動 ====
        writer = threading.Thread(target=writer_thread)
        writer.start()

        # ==== receive_data 起動 ====
        recv_thread = threading.Thread(target=receive_data, args=(handle,))
        recv_thread.start()
        receiver_ready.wait(timeout=3)

        # ==== logging_loop 起動 ====
        log_thread = threading.Thread(target=logging_loop)
        log_thread.start()
        logger_ready.wait(timeout=2)

        # --- 一括送信（1回のwriteで全部） ---
        print("送信要求コマンド送信")
        handle.write(cmds.encode())

        print(f"[MAIN] {RECORD_SECONDS}秒間記録します")
        print("[MAIN] Ctrl+Cで途中終了できます")

        start_time = time.time()
        stop_reason = "記録時間到達（自動停止）"

        try:
            while running:
                elapsed = time.time() - start_time

                # RECORD_SECONDSぴったりではなく、少し余裕を見て自動停止する
                if elapsed >= RECORD_SECONDS + AUTO_STOP_MARGIN_SEC:
                    print(
                        f"\n[MAIN] 記録時間 {RECORD_SECONDS} 秒 "
                        f"+ 余裕時間 {AUTO_STOP_MARGIN_SEC} 秒に達しました"
                    )
                    break

                time.sleep(0.5)

        except KeyboardInterrupt:
            stop_reason = "Ctrl+C"
            print("\n[MAIN] Ctrl+Cを検知しました")

        # ============================
        # 共通終了処理
        # 時間切れでも Ctrl+C でもここを通る
        # ============================
        print(f"[MAIN] 停止理由: {stop_reason}")
        print("[MAIN] ADio停止コマンドを送信します")

        if handle:
            try:
                command = "*F0000000#"
                print(f"command:{command}")
                handle.write(command.encode())
            except Exception as e:
                print("[MAIN] 停止コマンド送信でエラー:", e)

        # 受信スレッドを止める合図
        running = False

        print("[MAIN] 受信・変換・保存の残処理待ち...")

        # スレッド終了待ち
        if recv_thread.is_alive():
            recv_thread.join(timeout=2.0)

        if log_thread.is_alive():
            log_thread.join(timeout=5.0)

        if writer.is_alive():
            writer.join(timeout=5.0)

        print("[MAIN] 残処理待ち完了")

        print("\n===== CHUNK受信・保存結果 =====")

        for ch in range(REQUEST_DATA_NUM):
            expected = CHUNK_NUM
            received = recv_chunk_index[ch]
            saved = saved_chunk_count[ch]

            miss_recv = expected - received
            miss_save = received - saved

            status = "OK" if (received == expected and saved == expected) else "NG"

            print(f"CH{ch}: {status}")
            print(f"  受信: {received} / {expected}  (不足: {miss_recv})")
            print(f"  保存: {saved} / {expected}  (未保存: {miss_save})")

        print("===============================\n")

        print("\n===== 保存ファイル解析 =====")
        analyze_saved_file(BIN_FILE)
        print("==========================\n")

    finally:
        if handle:
            try:
                handle.close()
                print("[MAIN] ポートを閉じました。")
            except Exception as e:
                print("[MAIN] closeエラー:", e)
        handle = None

    print("[MAIN] 終了します。")


def load_saved_records(bin_file):
    records = []

    if not os.path.exists(bin_file):
        return records

    rec_size = 1 + 2 + 4 * CHUNK_SIZE  # uint8 + uint16 + float32 * CHUNK_SIZE
    file_size = os.path.getsize(bin_file)
    total_recs = file_size // rec_size

    with open(bin_file, "rb") as f:
        for _ in range(total_recs):
            data = f.read(rec_size)
            if len(data) != rec_size:
                break
            ch, idx = struct.unpack("<B H", data[:3])
            values = struct.unpack(f"<{CHUNK_SIZE}f", data[3:])
            records.append((ch, idx, values))

    return records


def analyze_saved_file(bin_file):
    print(f"[ANALYZE] 保存ファイル読み込み中: {bin_file}")

    if not os.path.exists(bin_file):
        print("[ANALYZE] ログファイルが存在しません")
        return

    records = load_saved_records(bin_file)
    if not records:
        print("[ANALYZE] 保存レコードがありません")
        return

    data_per_ch = defaultdict(list)
    index_per_ch = defaultdict(list)

    for ch, idx, vals in records:
        data_per_ch[ch].extend(vals)
        index_per_ch[ch].append(idx)

    print("\n----- 保存チャンク連続性チェック -----")
    for ch in range(REQUEST_DATA_NUM):
        indices = index_per_ch[ch]

        if not indices:
            print(f"CH{ch}: データなし")
            continue

        gaps = []
        duplicates = []
        backward = []

        prev = indices[0]
        for cur in indices[1:]:
            diff = cur - prev
            if diff == 1:
                pass
            elif diff > 1:
                gaps.append((prev, cur, diff - 1))
            elif diff == 0:
                duplicates.append(cur)
            else:
                backward.append((prev, cur))
            prev = cur

        status = "OK" if (not gaps and not duplicates and not backward) else "NG"
        print(f"CH{ch}: {status}")
        print(f"  saved_chunks  = {len(indices)}")
        print(f"  first_index   = {indices[0]}")
        print(f"  last_index    = {indices[-1]}")
        print(f"  gap_count     = {len(gaps)}")
        print(f"  duplicate_cnt = {len(duplicates)}")
        print(f"  backward_cnt  = {len(backward)}")

        if gaps:
            p, c, miss = gaps[0]
            print(f"  first_gap     = prev={p}, cur={c}, missing={miss}")
        if duplicates:
            print(f"  first_dup     = idx={duplicates[0]}")
        if backward:
            p, c = backward[0]
            print(f"  first_back    = prev={p}, cur={c}")

    print("------------------------------------")

    print("\n----- 保存データ周期チェック -----")
    fs = FS_KSPS * 1000

    for ch in range(REQUEST_DATA_NUM):
        signal = data_per_ch[ch]
        if len(signal) == 0:
            print(f"CH{ch}: データなし")
            continue

        cycles, est_freq, mean_interval, std_interval, min_interval, max_interval, intervals = \
            analyze_zero_cross_intervals(signal, fs, threshold=0.5)

        expected_freq = SIGNAL_FREQ

        print(f"CH{ch}:")
        print(f"  samples       = {len(signal)}")
        print(f"  cycles        = {cycles}")
        print(f"  estimated_freq= {est_freq:.6f} Hz")
        print(f"  expected_freq = {expected_freq:.6f} Hz")
        print(f"  mean_period   = {mean_interval * 1000:.6f} ms")
        print(f"  std_period    = {std_interval * 1000:.6f} ms")
        print(f"  min_period    = {min_interval * 1000:.6f} ms")
        print(f"  max_period    = {max_interval * 1000:.6f} ms")

        freq_ok = abs(est_freq - expected_freq) <= 2.0
        jitter_ok = (std_interval * 1000) <= 0.02

        if freq_ok and jitter_ok:
            print("  → OK")
        else:
            print("  → NG")

    print("---------------------------------")



def plot_saved_data(bin_file):
    print("[PLOT] ログファイル読み込み中...")
    records = []

    rec_size = 1 + 2 + 4 * CHUNK_SIZE  # uint8 + uint16 + float32 * CHUNK_SIZE
    file_size = os.path.getsize(bin_file)
    total_recs = file_size // rec_size

    with open(bin_file, "rb") as f:
        for _ in range(total_recs):
            data = f.read(rec_size)
            if len(data) != rec_size:
                break
            ch, idx = struct.unpack("<B H", data[:3])
            values = struct.unpack(f"<{CHUNK_SIZE}f", data[3:])
            records.append((ch, idx, values))

    # チャネルごとにデータまとめる
    data_per_ch = defaultdict(list)
    index_per_ch = defaultdict(list)

    for ch, idx, vals in records:
        data_per_ch[ch].extend(vals)
        index_per_ch[ch].append(idx)

    print("[PLOT] プロット開始...")
    plt.figure(figsize=(12, 8))
    for ch in sorted(data_per_ch.keys()):
        y = np.array(data_per_ch[ch])

        # チャンクインデックスを用いてX軸を作成
        # index_per_ch[ch] = [chunk_index0, chunk_index1, ...]
        indices = index_per_ch[ch]

        # チャンクごとにX軸を生成
        x = np.concatenate([
            np.linspace(idx, idx + 1, CHUNK_SIZE, endpoint=False)
            for idx in indices
        ])

        plt.plot(x, y, label=f"CH{ch}")

    plt.xlabel("Chunk Index")
    plt.ylabel("Voltage [V]")
    plt.title("ADC Log Data (X: Chunk Index)")
    plt.legend()
    plt.tight_layout()
    plt.grid(True)
    plt.show()




if __name__ == "__main__":
    import matplotlib.pyplot as plt  # ← 最後の描画でしか使わない
    import numpy as np               # 同上

    main()
    plot_saved_data(BIN_FILE)
