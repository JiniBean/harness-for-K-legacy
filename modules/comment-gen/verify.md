# C_COMMENT (변경 이력 주석)

| ID | 방법 | FAIL |
| :--- | :--- | :--- |
| C_COMMENT | 변경 파일 중 `[comment-gen] file_types`에 해당하는 파일에 `[comment-gen] format` 형식의 이력 주석이 있는지. `[comment-gen] exclude`(주석 금지 구간)는 제외 | 누락 |

- 형식·대상 파일·금지 구간은 `.agents/harness.toml`의 `[comment-gen]`를 Read해서 쓴다
- 주석 문구의 작성자는 `[person] author`
