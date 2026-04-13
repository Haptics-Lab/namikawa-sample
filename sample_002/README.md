## サンプル内容
NIのDAQでCSVにデータを記録するプログラム。

## ディレクトリ構成
```
sample_002/
├── main.py
│
├── src/           
│   └── ni_adc.py   ← 編集したデータ
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
必要なライブラリ(numpyとnidaqmx)が用意できていれば、`ni_adc.py`のみでも動きます。  
リポジトリから`ni_adc.py`をダウンロードして、ご自身のプロジェクト内で使用してください。  
```
sample_002 % uv add numpy nidaqmx
```

## 実行方法
### 方法1
`sample_002/`のフォルダごとコピーした方は`main.py`の実行で動きます。
```
sample_002 % uv run main.py
```
### 方法2
`ni_adc.py`をダウンロードした方は、`ni_adc.py`の実行で動きます。
```
sample_002 % uv run ni_adc.py
```