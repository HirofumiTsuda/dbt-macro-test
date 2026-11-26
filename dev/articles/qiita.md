<!--
Qiita に貼るもの
タイトル: dbt の macro をユニットテストする: YAML 1 ファイルと 1 コマンドで(dbt-macro-test)
タグ: dbt, ユニットテスト, Python, データエンジニアリング, CI
以下が本文。
-->

dbt 1.8 のネイティブな unit tests は **model** のテストです。入力の行と期待する行を書くと、dbt が比べてくれます。しかし、**macro** を呼ぶことはできません。`safe_divide` のような macro、slug を作る macro、`merge` を作る macro に、「この引数なら、これを返すはず」と書く方法は、dbt には用意されていません。

この不足は、[dbt-labs/dbt#10547](https://github.com/dbt-labs/dbt/issues/10547) で 2024 年 8 月から要望されていて、まだ開いたままです。この記事では、今ある方法と、そのために作った [dbt-macro-test](https://github.com/HirofumiTsuda/dbt-macro-test) を紹介します。

## 今ある方法と、その悩み

Qiita の[こちらの記事](https://qiita.com/n-gondo123/items/b33baeb75f5559aefbe2)が、この問題を使う側から、よくまとめています。macro を「SQL を作るもの」と「値を返すもの」に分けて、前者はテスト用の model と unit test の yml(手で3ファイル)、後者は `dbt_unittest` と `dbt run-operation` で試しています。そして、最後に2つの心配を挙げています。

- テスト用の model と macro が、プロジェクトの別々の場所に散らばる。
- `dbt run-operation` は macro の名前を指定するので、CI に組み込むには工夫が要る。

dbt-macro-test は、この2つに答える形で作りました。

| 方法 | やり方 | テストの置き場所 |
|---|---|---|
| macro を呼ぶ model と、その unit test を手で書く([解説](https://www.dumky.net/posts/unit-testing-dbt-macros-a-workaround-for-dbts-unit-testing-limitations/)) | macro の出力を model の出力にして、dbt が比べる | プロジェクトの `models/`(本物の model と同じ場所) |
| [`dbt-unittest`](https://github.com/yu-iskw/dbt-unittest) | `assert_equals` などの macro を `dbt run-operation` で動かす | プロジェクトの `macros/` |
| テスト専用のプロジェクト([`dbt-utils`](https://github.com/dbt-labs/dbt-utils/tree/main/integration_tests) など) | 専用の seed、model、テスト | 別のプロジェクト(手で保守) |
| [`pytest-dbt-core`](https://github.com/godatadriven/pytest-dbt-core) | pytest のプラグイン | Python のファイル |

## 考え方: 1つ目の方法を、生成する

dbt-macro-test は、1つ目の方法を自動にしたものです。YAML で仕様を書くと、ケースごとに、macro を呼ぶ使い捨ての model と、その model の dbt ネイティブの unit test を、一時ディレクトリの dbt プロジェクトに作って、dbt に走らせます。プロジェクトには何も足さず、**実行も、比較も、失敗時の差分も、dbt のもの**です。

```bash
pip install dbt-duckdb        # プロジェクトで使っているアダプター
pip install dbt-macro-test
```

macro:

```sql
-- macros/safe_divide.sql
{% macro safe_divide(numerator, denominator) %}
    {{ numerator }} / nullif({{ denominator }}, 0)
{% endmacro %}
```

仕様(`macro_test/safe_divide.yml`):

```yaml
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

(dbt の起動時の行とタイムスタンプは省いています。)ケースが失敗すると、dbt 自身の差分が出て、終了コードは 1 になります。

```console
actual differs from expected:

@@ ,result
+++,Decimal('2.5')
---,Decimal('2.0')

1 failed, 1 passed
```

## 値だけではない

どれも、リポジトリのサンプルプロジェクトで、実際に動かしたものです。

**エラーで止まる macro**(メッセージは、含まれていればよい):

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

**model や source を読む macro。** `ref('orders')` を呼ぶ macro は、`orders` が存在する必要があります。しかし、生成するプロジェクトには、手元の model はありません。macro に見せる行を、仕様に書きます。本物のデータは読みません。

```yaml
        given:
          arguments: {status: "'open'"}
          inputs:
            - input: ref('orders')
              rows:
                - {id: 1, status: open}
                - {id: 2, status: shipped}
```

そのほか、**パッケージの macro**(`dbt_utils.slugify` のようにパッケージ名つきで書きます)、**SQL ではない文字列を返す macro**(`output: text`)、ケースごとの `vars`、環境変数、別の macro の差し替え(`overrides`)、期待する行を csv や select、ファイルで書くこと、が使えます。

**書き込む macro**(insert、merge、delete)は、ケースの関係(テーブル)を一時的なものとして作り、macro を走らせて、そのあとに、クエリが返す行を比べて、最後に削除します。これは**対象のスキーマへの実際の書き込み**なので、手元や使い捨てのターゲットで使ってください。

[使い方の案内](https://hirofumitsuda.github.io/dbt-macro-test/guide/)に、macro の種類ごとの例があります。すべて CI で動かしています。

## CI で使う

コマンドは1つで、終了コードがあります。0 は全部通った、1 は失敗したケースがある、2 はテストを走らせられなかった(仕様の誤り、引数名の誤り、dbt 自体の失敗)です。`--select "safe_*::by_zero"` で、一部のケースだけ走らせられます。`dbt test` と同じものが必要です。アダプターと profile です。unit test はウェアハウスで走るので、CI のジョブには、書き込めるスキーマでの `dbt run` と同じ権限が要ります。

## できないこと

先に書いておきます。

- **動かしたのは duckdb だけです。** 実行は dbt に任せているので、ほかのアダプターでも動く可能性はありますが、試していません。
- **alpha(0.2)** で、仕様の形はまだ変わるかもしれません。dbt-core 1.8 以上、Python 3.11 以上です。dbt を同じプロセスで動かすので、アダプターを同じ環境に入れる必要があります。
- dbt Fusion で動くかは分かりません(dbt-core をプロセス内で動かします)。ウェアハウスに接続せずに、macro の戻り値だけを確かめることもできません。

## リンク

- リポジトリ: <https://github.com/HirofumiTsuda/dbt-macro-test>
- PyPI: <https://pypi.org/project/dbt-macro-test/>
- ドキュメント: <https://hirofumitsuda.github.io/dbt-macro-test/>

別の方法で macro をテストしている方、これでは書けない macro がある方は、リポジトリの issue で教えてください。
