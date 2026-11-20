# AI development template

小人数チームで新規プロジェクトを始めるためのテンプレート。配布版 0.1.0。UbuntuまたはWSL2でGit・Python 3・Shellを用意する。

1. GitHubのテンプレート生成またはリポジトリのコピーで新規プロジェクトを用意し、cloneする。
2. `harness/bootstrap.sh --dry-run` で確認し、`harness/bootstrap.sh` で初期化する。
3. チームと目的、環境、必須チェック・対象外の理由、レビュー担当を決める。harness/project.jsonに version（1）と checks 配列を記載する。各項目は id、argv（引数配列）、required（真偽値）、任意の depends（ID配列）と timeout（秒）。実プロジェクトのテストコマンドを登録する。
4. `harness/verify.sh --target project` を実行する。表示された結果ディレクトリを `harness/evaluate.sh --target project --results DIR` に渡す。終了コードは成功0、失敗1、検証不能2、未設定3。
5. 共通基盤は `harness/verify.sh --target template`、Secret検出は `python3 harness/scan.py`。検出対象は秘密鍵ヘッダ、GitHubトークンの一部、AWSアクセスキーID。失敗時はローカルで対象コマンドを再実行する。

標準フローにはSpec Kit v1.4.3のCodex統合を同梱した。確認版はCodex CLI 0.164.0。利用先で $speckit-constitution、$speckit-specify、$speckit-plan、$speckit-tasks を順に使用し、合意後に $speckit-implement と $speckit-converge を使用する。追加タスクは予算内で実装して再検証する。

GitHubのTemplate Repository指定、Rulesets、必須レビュー、CODEOWNERSは管理者が利用先で確認する。利用先ではprojectとsecurityを必須チェックに設定する。未設定のprojectジョブは終了3で失敗する。

更新時は導入版を記録し、配布版間のgit diffを確認してPRで取り込む。Spec Kit更新時は空の一時ディレクトリで固定版を生成し差分を確認する。ローカルの変更と競合した場合は手動で統合する。
