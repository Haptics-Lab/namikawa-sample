## サンプル内容
NIのDAQを使った以下のサンプルを含みます。

- `ni_adc.py`: アナログ入力をCSVに記録
- `ni_counter.py`: カウンタ出力でパルス信号を生成
- `ni_do.py`: デジタル出力で同期信号を生成

## ディレクトリ構成
```
sample_002/
├── main.py
│
├── src/
│   ├── ni_adc.py
│   ├── ni_counter.py
│   └── ni_do.py
│
├── output/         ← 結果など
│
└── README.md
```

## 環境構築
OSはWindowsを想定しています。  
uvを使用します。uvの導入までは事前に行ってください。  
また、必要に応じてNI-DAQmx driverをインストールしてください。  

### 方法1
`sample_002/`をPCにコピーして、以下のコマンドを実行してください。
```
sample_002 % uv sync
```
### 方法2（推奨）
必要なライブラリ(`nidaqmx`、必要に応じて`numpy`)が用意できていれば、`src/`配下の各ファイル単体でも動きます。  
リポジトリから必要なファイルをダウンロードして、ご自身のプロジェクト内で使用してください。  
```
sample_002 % uv add numpy nidaqmx
```

## 実行方法
### 方法1
`sample_002/`のフォルダごとコピーした方は、`main.py`の実行で動きます。
```
sample_002 % uv run main.py
```

`main.py`ではデフォルトで`main_adc()`を実行します。  
`main_counter()`や`main_do()`を使う場合は、`main.py`内のコメントを切り替えてください。

### 方法2
`src/`配下の各ファイルは単体でも実行できます。
```
sample_002 % uv run src/ni_adc.py
sample_002 % uv run src/ni_counter.py
sample_002 % uv run src/ni_do.py
```