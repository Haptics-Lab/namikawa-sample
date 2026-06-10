## サンプル内容
ADioを使って、PWM出力とアナログ入力の取得を行うサンプルです。

- `main.py` : ADIOの初期化、PWM出力、ADCデータのCSV保存。
- `src/adio_pwm.py` : GPIOのPWM出力制御
- `src/adio_adc.py` : アナログ入力データの取得とCSV保存
- `src/adio_transport.py` : FTDI経由の通信処理

`main.py` では、ADioのデジタル出力1chをPWM出力に設定し、複数のアナログ入力チャンネルを同時に取得して `output/adio_data.csv` に保存します。

## ディレクトリ構成
```
sample_009/
├── main.py
├── src/
│   ├── adio_adc.py
│   ├── adio_pwm.py
│   └── adio_transport.py
├── output/         ← 計測結果の出力先
└── README.md
```

## 環境構築
パッケージ管理にはuvを使用します（uv自体は事前に導入してください）。
また、FTDI D2XX driverのインストールを事前に行ってください。

`sample_009/` をPCにコピーし、以下のコマンドを実行します。

```bash
sample_009 % uv sync
```

## 実行前の設定（main.py）
機器構成に合わせて `main.py` の設定を書き換えてください。

### 1. 接続するADIOのシリアル番号
```python
io = ADioTransport(serial="FT9IK4VX")
```

シリアル番号は下記のプログラムで確認できます。
```python
print(ADioTransport.list_serials())
```

### 2. PWM出力設定
出力ビット、周波数、デューティ比を設定します。
```python
adio_pwm_config = ADioPWMConfig(
	gpio_bit=0,
	freq_hz=1,
	duty=0.40,
)
```

### 3. ADC 取得設定
サンプリング周波数、データ要求周期、対象チャンネル、入力レンジを設定します。
```python
adio_adc_config = ADioADCConfig(
	fs=16000,
	chunk_rate_hz=200,
	request_chunks_per_command=50,
	channels={
		0: "Tactile LI",
		1: "Tactile LT",
		2: "Tactile RI",
		3: "Tactile RT",
		5: "EMG LE",
		6: "EMG LF",
		7: "EMG RE",
		8: "EMG RF",
		10: "Sync Signal",
	},
	input_range=5.0,
)
```

### 4. 出力先 CSV
計測データの保存先を設定します。
```python
adc.stream_to_csv(Path("output") / "adio_data.csv")
```

## 実行方法
`sample_009/` で以下を実行します。

```bash
uv run main.py
```

## 実行フロー
1. ADioに接続し、全チャンネル設定を初期化
2. PWM出力設定を反映
3. ADCデータ取得を開始し、`output/adio_data.csv` に逐次保存
4. Enterキーを押すと計測停止

## 出力ファイル
実行後、以下のようなCSVが出力されます。

- `output/adio_data.csv`

CSVには以下の列が含まれます。

- `Sample Index`
- `Time [sec]`
- 各チャンネル名（例: `Tactile LI`, `EMG LE`, `Sync Signal`）

## 補足
`src/adio_adc.py` と `src/adio_pwm.py` は単体実行も可能です。個別に動作確認したい場合は、各ファイル内の設定を書き換えて実行してください。

```bash
uv run -m src.adio_pwm
uv run -m src.adio_adc
```
