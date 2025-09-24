# JPX Financial Summary Loader

このリポジトリには、日本の上場企業が公開している決算短信（XBRL）をダウンロードし、
主要な財務指標を抽出して SQL Server に保存する Python スクリプトが含まれています。

## セットアップ

1. 必要なライブラリをインストールします。

   ```bash
   pip install -r requirements.txt
   ```

2. SQL Server に接続できる環境（ODBC ドライバーなど）が整っていることを確認してください。

## 使い方

```bash
python src/main.py \
  --ticker 7203 \
  --from-date 2023-01-01 \
  --to-date 2023-12-31 \
  --server <SQLSERVER_HOST> \
  --database <DATABASE_NAME> \
  --username <USER> \
  --password <PASSWORD>
```

- `--ticker` は 4 桁の東証コードです。省略した場合は指定期間内のすべての決算短信が対象になります。
- `--from-date`, `--to-date` は EDINET API に渡す提出日（YYYY-MM-DD）です。
- SQL Server 接続情報を正しく指定してください。`--odbc-driver` でドライバー名を明示することもできます。

## 処理内容

1. EDINET API を用いて指定期間の決算短信を検索します。
2. XBRL ファイルをダウンロードし、売上高・営業利益・経常利益・純利益を四半期別に抽出します。
3. SQL Server 上の `dbo.JpxFinancials` テーブルに upsert（挿入/更新）します。

テーブルが存在しない場合は自動的に作成されます。既存データがある場合は `Ticker`、`FiscalYear`、`FiscalQuarter`
の組み合わせで更新されます。

## 注意事項

- EDINET の仕様変更等によりフォームコードやタグ名が変わる可能性があります。
- ネットワーク状況や EDINET の利用制限によりダウンロードに失敗することがあります。その場合でもログにエラーが出力され、処理は継続されます。
- SQL Server への接続には ODBC ドライバーが必要です。Linux 環境の場合は Microsoft が提供する `msodbcsql17` などを事前にインストールしてください。
