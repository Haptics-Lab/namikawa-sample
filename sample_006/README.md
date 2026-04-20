## サンプル内容
NI DAQ、マイク、カメラ（MocapForAll）、Motive（NatNet）を同時に使用して、複数のセンサからデータを並列取得・保存するプログラム。

- **NI DAQ** : アナログ入力チャンネルのデータをCSVに保存（sample_002 ベース）
- **Audio** : マイクで録音し、WAVファイルに保存（sample_003 ベース）
- **MocapForAll Cameras** : 複数カメラで録画し、MP4ファイルに保存（sample_004 ベース）
- **Motive** : marker set および rigid body のデータをCSVに保存（sample_005 ベース）

各センサのworderは別スレッドで動作し、`stop_event` によって一斉停止します。

## ディレクトリ構成
```
sample_006/
├── main.py
│
├── src/
│   ├── ni/
│   │   └── ni_adc.py
│   ├── audio/
│   │   └── audio_recorder.py
│   ├── mfa/
│   │   └── camera_recorder.py
│   └── motive/
│       ├── marker_set.py
│       ├── rigid_body.py
│       ├── natnet_stream.py
│       └── fromSDK/
│
├── output/         ← 結果など
│
└── README.md
```

## 環境構築
OSはWindowsを想定しています。  
uvを使用します。uvの導入までは事前に行ってください。  
また、必要に応じてNI-DAQmx driverをインストールしてください。  
Motive 側で NatNet Streaming を有効にし、接続先の IP アドレスを確認してください。  

`sample_006/`をPCにコピーして、以下のコマンドを実行してください。
```
sample_006 % uv sync
```

## 実行方法
接続先や機器の設定に応じて `main.py` 内の各 Config を変更してください。

### NI DAQ の設定
使用するchannel・label・rangeを `ChannelConfig` で指定します。  
また、NIのデバイス名とサンプリング周波数を指定します。
```python
channel_configs = [
	ChannelConfig(ch="ai0", ch_label="Tactile LI", terminal_config=TerminalConfiguration.RSE, voltage_range=(-2.0, 2.0)),
	...
]
ni_adc = NIADC(device_name="Dev1", sampling_rate=16000.0, ...)
```

### Audio の設定
使用するデバイス番号・サンプリング周波数・チャンネル数を指定します。
```python
audio_recorder = AudioRecorder(device=2, sample_rate=44100, channels=2, blocksize=1024)
```

### カメラの設定
使用するカメラのデバイス番号・解像度・フレームレートを `CameraConfig` で指定します。
```python
multi_camera_recorder = MultiCameraRecorder(configs=[
	CameraConfig(device=0, width=640, height=480, fps=30),
	...
])
```

### Motive の設定
Motive 側のストリーミング設定で unicast にしている場合は、`use_multicast=False` にしてください。
```python
natnet_config = NatNetConfig(
	client_ip="127.0.0.1",
	server_ip="127.0.0.1",
	use_multicast=False,
)
```

### 実行
```
sample_006 % uv run main.py
```
