## サンプル内容
皮膚振動の伝達関数を測定するサンプル。

各指（`LI`：左手人差し指, `LT`：左手親指, `RI`：右手人差し指, `RT`：右手親指）について、白色雑音を3回提示しながら計測を行い、計測後に自動で伝達関数を導出。  
データの記録にはADioを使用。

## ディレクトリ構成
```
sample_010/
├── main.py
├── src/
│   ├── measurement/
│   │   ├── adio/
│   │   │   ├── adio_adc.py
│   │   │   └── adio_transport.py
│   │   ├── sound/
│   │   │   ├── sound_player.py
│   │   │   └── whitenoise_sample.wav
│   │   └── finger_measurement.py
│   ├── analysis/
│   │   └── transfer_function_analyzer.py
│   └── plot/
│       ├── live_plot_processor.py
│       └── live_plotter.py
├── output/
│   ├── raw/       ← 生データ CSV
│   └── processed/ ← 解析結果（Excel, txt, png）
└── README.md
```

## 環境構築
パッケージ管理にはuvを使用します（uv 自体は事前に導入してください）。
また、ADio利用のためFTDI D2XX driverを事前にインストールしてください。

`sample_010/` をコピーし、以下を実行します。

```bash
uv sync
```

## 実行前の設定（main.py）
機器構成や解析条件に合わせて `main.py` の設定を変更してください。

### 1. ADio シリアル番号
```python
DEVICE_SERIAL = "FT9IK4VX"
```

シリアル番号は下記で確認できます。
```python
print(ADioTransport.list_serials())
```

### 2. 計測対象指
実行対象の指を設定します。
```python
FINGERS = ("LI", "LT", "RI", "RT")
```

### 3. チャンネル割り当て
ADio の入力チャンネルとラベルを設定します。
```python
CHANNELS = {
	0: "Tactile LI Output",
	1: "Tactile LT Output",
	2: "Tactile RI Output",
	3: "Tactile RT Output",
	5: "Tactile Finger Input",
	6: "Force",
}
```

### 4. 力覚換算
Forceチャンネル値の換算式を設定します。
```python
def force_converter(raw_value: float) -> float:
	return 1.1332 * raw_value
```

### 5. 計測設定
`FingerMeasurement` の以下パラメータを用途に応じて調整します。

- `sampling_rate`
- `chunk_rate_hz`
- `request_chunks_per_command`
- `input_range`
- `trial_count`
- `live_plot_enabled`
- `live_plot_window_seconds`
- `live_plot_y_limits`
- `live_plot_y_band`

### 6. 解析設定
`TransferFunctionAnalyzer` の以下パラメータを用途に応じて調整します。

- `window_sec`
- `window_count`
- `analysis_start_offset_sec`
- `analysis_end_offset_sec`
- `plot_x_limits`

## 実行方法
`sample_010/` で以下を実行します。

```bash
uv run main.py
```

## 実行フロー
1. ADioに接続して初期化
2. 指ごとに計測を開始（`LI` → `LT` → `RI` → `RT`）
3. 各指で Enterキーを押すたびに白色雑音を再生し、3試行分のデータを記録
4. 計測中は Forceチャンネルをライブプロット表示
5. 指ごとの計測終了後に伝達関数を解析し、結果を保存
6. 全指終了後にADio接続をクローズ

## 出力ファイル例
指ごとに以下のファイルが出力されます。

- `output/raw/LI.csv`
- `output/processed/LI_selected_windows.txt`
- `output/processed/LI_processed_data.xlsx`
- `output/processed/LI_transfer_function.xlsx`
- `output/processed/LI_linear_transfer_function.png`
- `output/processed/LI_db_transfer_function.png`

`LT`, `RI`, `RT` についても同様のファイルが生成されます。
