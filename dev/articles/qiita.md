<!--
Qiita に貼るもの
タイトル: dbt の macro をユニットテストする(dbt-macro-test)
タグ: dbt, ユニットテスト, Python, データエンジニアリング, CI
以下が本文。
-->

dbt 1.8 の unit tests は model 用です。入力の行と期待する行を書くと、dbt が比べます。macro に引数を渡して結果を確かめることは、同じ形ではできません。[dbt-labs/dbt#10547](https://github.com/dbt-labs/dbt/issues/10547) で 2024 年 8 月から要望されていますが、まだ開いたままです。

今は回避策を使います。macro を呼ぶだけの model を作って、その model に unit test を書く方法があります([こちらの記事](https://www.dumky.net/posts/unit-testing-dbt-macros-a-workaround-for-dbts-unit-testing-limitations/))。[dbt-unittest](https://github.com/yu-iskw/dbt-unittest) の assert 用 macro を `dbt run-operation` で動かす方法もあります。dbt-utils は別プロジェクト([integration_tests](https://github.com/dbt-labs/dbt-utils/tree/main/integration_tests))でテストしていて、[pytest-dbt-core](https://github.com/godatadriven/pytest-dbt-core) なら Python から macro をテストできます。

Qiita の[この記事](https://qiita.com/n-gondo123/items/b33baeb75f5559aefbe2)は、前の2つを試して、最後に2つの懸念を挙げています。テスト用のファイルがプロジェクトに散らばること、そして `run-operation` は macro の名前を指定するので、CI に入れるのに工夫が要ることです。

[dbt-macro-test](https://github.com/HirofumiTsuda/dbt-macro-test) は、1つ目の方法のテストを、YAML の仕様から作ります。ケースごとに、macro を呼ぶ使い捨ての model と dbt ネイティブの unit test を、一時ディレクトリのプロジェクトに生成して、dbt に走らせます。プロジェクトには何も足しません。実行も、比較も、差分の表示も、dbt のものです。仕様は1つの YAML で、実行は1つのコマンドです。

## 最初のテスト

```bash
pip install dbt-duckdb        # プロジェクトで使っているアダプター
pip install dbt-macro-test
```

```sql
-- macros/safe_divide.sql
{% macro safe_divide(numerator, denominator) %}
    {{ numerator }} / nullif({{ denominator }}, 0)
{% endmacro %}
```

```yaml
# macro_test/safe_divide.yml
macros:
  - macro: safe_divide
    cases:
      - name: plain_division
        given:
          arguments: {numerator: 10, denominator: 4}
        expect:
          rows:
            - {result: 2.5}      # macro の出力は result 列
      - name: division_by_zero_is_null
        given:
          arguments: {numerator: 10, denominator: 0}
        expect:
          rows:
            - {result: null}
```

```console
$ dbt-macro-test run
1 of 2 PASS _dmt_safe_divide_safe_divide_division_by_zero_is_null::division_by_zero_is_null  [PASS in 0.08s]
2 of 2 PASS _dmt_safe_divide_safe_divide_plain_division::plain_division ........ [PASS in 0.02s]
Done. PASS=2 WARN=0 ERROR=0 SKIP=0 NO-OP=0 REUSED=0 TOTAL=2

2 passed
```

dbt の起動時の行とタイムスタンプは省いています。期待値が間違っていると、dbt 自身の差分が出て、終了コードは 1 になります。

```console
actual differs from expected:

@@ ,result
+++,Decimal('2.5')
---,Decimal('2.0')

1 failed, 1 passed
```

## エラー、ref、そのほか

エラーで止まる macro もテストできます。メッセージは、エラーに含まれていれば通ります。

```yaml
  - macro: quantity
    cases:
      - name: stops_with_an_error_when_it_is_negative
        given:
          arguments: {value: -5}
        expect:
          error:
            message: quantity must not be negative, got -5
```

`ref('orders')` や `source(...)` を呼ぶ macro には、仕様の中で行を渡します。本物のデータは読みません。期待する行は、csv、select、ファイルでも書けます。パッケージの macro は `dbt_utils.slugify` のようにパッケージ名つきで書きます。ケースごとに、`vars`、環境変数、別の macro を差し替えられます。SQL ではない文字列(slug など)は、文字列として比べます。insert、merge、delete をする macro は、ケースごとに一時的な関係を作って確かめます。これは対象のスキーマへの実際の書き込みなので、手元か使い捨てのターゲットで使ってください。[使い方の案内](https://hirofumitsuda.github.io/dbt-macro-test/guide/)に、それぞれの例があり、すべて CI で動かしています。

## CI と、まだできないこと

`dbt-macro-test run` の終了コードは、全部通れば 0、失敗したケースがあれば 1、仕様の誤りなどで走らせられなければ 2 です。`--select "safe_*::by_zero"` で一部だけ走らせられます。unit test はウェアハウスで走るので、CI のジョブにはアダプターと profile、書き込めるスキーマでの `dbt run` と同じ権限が要ります。

動かしたのは duckdb だけです。実行は dbt に任せているので、ほかのアダプターでも動くかもしれませんが、試していません。バージョンは 0.2 で、仕様の形はまだ変わるかもしれません。dbt-core 1.8 以上と Python 3.11 以上が必要で、dbt を同じプロセスで動かすため、アダプターは同じ環境に入れます。dbt Fusion で動くかは分かりません。

- リポジトリ: <https://github.com/HirofumiTsuda/dbt-macro-test>
- PyPI: <https://pypi.org/project/dbt-macro-test/>
- ドキュメント: <https://hirofumitsuda.github.io/dbt-macro-test/>
