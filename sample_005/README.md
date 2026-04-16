## サンプル内容
Motive からデータを受信し、CSVに保存するプログラム。
NatNet SDK の v4.4.0 をベースにしています。

### marker set
- marker set の座標を受信する
- 壁時計の時刻と Motive 側の時刻を付けて CSV に保存する
- marker set ごとに 1 ファイルずつ出力する

出力先は `output/marker_sets/` です。  
各 CSV は `wallclock_timestamp`, `motive_timestamp`, `*_x`, `*_y`, `*_z` の列を持ちます。

### rigid body
- rigid body の位置と姿勢を受信する
- 壁時計の時刻と Motive 側の時刻を付けて CSV に保存する
- rigid body ごとに 1 ファイルずつ出力する

出力先は `output/rigid_bodies/` です。  
各 CSV は `wallclock_timestamp`, `motive_timestamp`, `x`, `y`, `z`, `qx`, `qy`, `qz`, `qw` の列を持ちます。

### skeleton
- skeleton のボーン情報を受信する
- 構造情報と時系列データを CSV に保存する
- skeleton ごとに structure 用と data 用の2ファイルを出力する

出力先は `output/skeletons/` です。  
`*_structure.csv` にボーン構造、`*_data.csv` にボーンごとの位置・姿勢データを保存します。


## ディレクトリ構成
```
sample_005/
├── main.py
│
├── src/
│   ├── marker_set.py
│   ├── rigid_body.py
│   ├── skeleton.py
│   ├── natnet_stream.py
│   └── fromSDK/
│
├── output/         ← 結果など
│
└── README.md
```

## 環境構築
uvを使用します。uvの導入までは事前に行ってください。  
Motive 側で NatNet Streaming を有効にし、接続先の IP アドレスを確認してください。  

### 方法1
`sample_005/`をPCにコピーして、以下のコマンドを実行してください。
```
sample_005 % uv sync
```

### 方法2（推奨）
このサンプルは標準ライブラリと同梱の NatNet SDK ファイルを使用しています。  
必要なファイルを自分のプロジェクトにコピーして使用してください。  
例えば、rigid body を扱う場合は、`natnet_stream.py`と`fromSDK/`と`rigid_body.py`が必要です。

- `natnet_stream.py`
- `marker_set.py`
- `rigid_body.py`
- `skeleton.py`
- `fromSDK/`


## 実行方法
接続先に応じて `NatNetConfig` の IP アドレスを設定してください。  
Motive 側のストリーミング設定で unicast にしている場合は、`use_multicast=False`にしてください。

```python
natnet_config = NatNetConfig(
	client_ip="127.0.0.1",
	server_ip="127.0.0.1",
	use_multicast=False,
)
```
取得したデータをコマンドプロンプトに表示する場合は`print_enabled=True`、表示しない場合は`print_enabled=False`にしてください。  
`csv_folder_path=None`にすると、CSVへの出力は行われません。

### 方法1
`sample_005/`のフォルダごとコピーした方は、`main.py`の実行で動きます。
```
sample_005 % uv run main.py
```

`main.py` の中で、実行したいストリーム処理を選んでください。

```python
# stream_rigid_bodies(config=natnet_config)
# stream_skeletons(config=natnet_config)
stream_marker_sets(config=natnet_config)
```

### 方法2
各ファイルを個別に実行することもできます。
```
sample_005 % uv run marker_set.py
sample_005 % uv run rigid_body.py
sample_005 % uv run skeleton.py
```
