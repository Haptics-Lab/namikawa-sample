## サンプル内容
NI DAQ、マイク、カメラ（MocapForAll）、Motive（NatNet）、脳波測定装置を同時に使用して、複数のセンサからデータを並列取得・保存するプログラム。

- **NI DAQ** : アナログ入力チャンネルのデータをCSVに保存（sample_002 ベース）
- **Audio** : マイクで録音し、WAVファイルに保存（sample_003 ベース）
- **MocapForAll Cameras** : 複数カメラで録画し、MP4ファイルに保存（sample_004 ベース）
- **Motive** : marker set および rigid body のデータをCSVに保存（sample_005 ベース）
- **EEG** : EEG のデータをCSVに保存（sample_008 ベース）


各 recorder は別スレッドで動作し、共通の stop 制御で一斉停止します。  
EEG はサブプロセス（src.eeg.eeg_processor）として起動し、標準入力コマンドで制御します。

## ディレクトリ構成
```
sample_006/
├── main.py
├── src/
│   ├── ni/
│   │   ├── ni_adc.py
│   │   └── ni_counter.py
│   ├── audio/
│   │   └── audio_recorder.py
│   ├── mfa/
│   │   └── camera_recorder.py
│   ├── motive/
│   │   ├── marker_set.py
│   │   ├── rigid_body.py
│   │   ├── natnet_stream.py
│   │   └── fromSDK/
│   └── eeg/
│       ├── eeg_recorder.py
│       └── eeg_processor.py
├── output/  ← 記録データ出力先
└── README.md
```

## 環境構築
OS は Windows を想定しています。  
パッケージ管理には uv を使用します（uv 自体は事前に導入してください）。

必要に応じて以下を準備してください。

- NI-DAQmx driver
- Motive 側の NatNet Streaming 設定（IP / unicast または multicast）
- EEG 機器ドライバ・通信環境（COM ポート確認）

sample_006/ をコピーして以下を実行します。

```bash
uv sync
```

## 実行前の設定（main.py）
機器構成に合わせて main.py の設定を書き換えてください。

### 1. 出力先フォルダ
```python
raw_data_folder = Path("output") / "participant01" / "trial01"
```

### 2. 記録対象の有効/無効
```python
recording_bool = {
	"NI DAQ": True,
	"Audio": True,
	"MocapForAll Cameras": False,
	"Motive MarkerSets": False,
	"Motive RigidBodies": False,
	"EEG": True,
}
```

### 3. 同期信号（NI Counter）
同期信号出力の有効/無効を切り替えます。
```python
sync_signal_bool = True
```

### 4. NI DAQ
使用チャネル、ラベル、電圧レンジ、デバイス名、サンプリング周波数を設定します。
```python
ni_adc = NIADC(
	device_name="Dev1",
	sampling_rate=16000.0,
	...
)
```

### 5. Audio
デバイス番号、サンプリング周波数、チャンネル数を設定します。
```python
audio_recorder = AudioRecorder(device=5, sample_rate=44100, channels=2, blocksize=1024)
```

### 6. カメラ（MocapForAll）
カメラ番号・解像度・fps を CameraConfig で指定します。

### 7. Motive / NatNet
Motive 側設定に合わせて client_ip、server_ip、use_multicast を設定します。
```python
natnet_config = NatNetConfig(
	client_ip="127.0.0.1",
	server_ip="127.0.0.1",
	use_multicast=False,
)
```

### 8. EEG
接続 COM ポートを設定します。
```python
eeg_config = EEGConfig(com_port="COM3")
```

## 実行
sample_006/ で以下を実行します。

```bash
uv run main.py
```

## 実行フロー
### EEG を有効にした場合
1. Enter でインピーダンスチェック開始
2. Enter でインピーダンスチェック停止 + 記録開始
3. 全 recorder 起動後に同期信号が出力される
4. 計測を終えたいタイミングで Enter を押す（この Enter で同期信号を停止）
5. 同期信号停止後、約 3 秒待ってから全記録を終了

### EEG を無効にした場合
1. Enter で各 recorder の記録開始
2. 全 recorder 起動後に同期信号が出力される
3. 計測を終えたいタイミングで Enter を押す（この Enter で同期信号を停止）
4. 同期信号停止後、約 3 秒待ってから全記録を終了

## 出力ファイル例
設定と有効化状況に応じて、例えば以下が出力されます。

- ni_data.csv
- audio_data.wav
- eeg_data.csv
- mfa/（カメラ動画）
- motive/marker_sets/*.csv
- motive/rigid_bodies/*.csv
