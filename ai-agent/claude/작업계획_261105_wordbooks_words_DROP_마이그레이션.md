# wordbooks / words 테이블 DROP 마이그레이션 계획 (D단계-2) — 승인 대기

- 작성일: 2026-11-05 / 브랜치: `feature/central-vocab`
- 상태: **계획 보고만 완료. 백업·alembic upgrade·코드 삭제는 모두 승인 후 실행한다.**

## 1. 현황 (SELECT 로 확인한 사실)

| 항목 | 값 |
| :--- | :--- |
| DB 현재 리비전 | `c3f7a9d1e8b2` (alembic head 와 동일) |
| `words` → `wordbooks` FK | `fk_words_wordbook` (ON DELETE CASCADE) |
| `wordbooks` → `users` FK | `fk_wordbooks_user` (ON DELETE CASCADE) |
| `words`/`wordbooks` 를 참조하는 다른 테이블 | 없음 (study_logs·bookmarks·quiz_sessions 는 C 이전 마이그레이션에서 `system_words` 로 전환 완료) |
| 현재 행 수 | `wordbooks` 1건, `words` 0건 (개발 DB, 실사용자 없음) |

DROP 순서는 자식 → 부모(`words` → `wordbooks`)여야 한다.

## 2. 백업 명령 (승인 후 실행, 결과는 git 무시 경로 `ai-agent/backups/`)

컨테이너 `voda-voca-mysql` 안의 환경변수를 쓰므로 비밀번호가 명령 이력에 남지 않는다.

```bash
# (a) DROP 대상 2개 테이블만 — 구조 + 데이터
docker exec voda-voca-mysql sh -c \
  'mysqldump -uroot -p"$MYSQL_ROOT_PASSWORD" --single-transaction --routines --no-tablespaces \
   "$MYSQL_DATABASE" wordbooks words' \
  > ai-agent/backups/backup_pre_d_drop_wordbooks_words_261105.sql

# (b) 전체 DB — 롤백 보험
docker exec voda-voca-mysql sh -c \
  'mysqldump -uroot -p"$MYSQL_ROOT_PASSWORD" --single-transaction --routines --no-tablespaces \
   "$MYSQL_DATABASE"' \
  > ai-agent/backups/backup_full_pre_d_261105.sql

# 검증: 파일이 비어 있지 않고 두 테이블의 CREATE 문이 들어 있는지
grep -c "CREATE TABLE" ai-agent/backups/backup_pre_d_drop_wordbooks_words_261105.sql   # 기대값 2
```

복구가 필요하면: `docker exec -i voda-voca-mysql sh -c 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" "$MYSQL_DATABASE"' < (a 파일)`.

## 3. 마이그레이션 DDL (신규 리비전 `d1_drop_legacy_wordbooks_words`, down_revision=`c3f7a9d1e8b2`)

### upgrade
```sql
DROP TABLE words;       -- fk_words_wordbook 이 함께 사라진다
DROP TABLE wordbooks;
```
Alembic: `op.drop_table("words")`, `op.drop_table("wordbooks")`.

### downgrade (구조만 복원, 데이터는 2절 백업으로 복구)
최초 스키마(`08e3374f8644`) + `4454ed2683cb`(example_meaning) 와 동일한 형태로 재생성한다.
```sql
CREATE TABLE wordbooks (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  user_id BIGINT UNSIGNED NOT NULL,
  name VARCHAR(50) NOT NULL,
  description VARCHAR(200) NULL,
  created_at DATETIME(3) NOT NULL DEFAULT (UTC_TIMESTAMP(3)),
  updated_at DATETIME(3) NOT NULL DEFAULT (UTC_TIMESTAMP(3)),
  PRIMARY KEY (id),
  UNIQUE KEY uk_wordbooks_user_name (user_id, name),
  KEY idx_wordbooks_user_updated (user_id, updated_at),
  CONSTRAINT fk_wordbooks_user FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
  CONSTRAINT ck_wordbooks_name_not_blank CHECK (CHAR_LENGTH(TRIM(name)) > 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE words (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  wordbook_id BIGINT UNSIGNED NOT NULL,
  term VARCHAR(100) NOT NULL,
  meaning VARCHAR(200) NOT NULL,
  example VARCHAR(500) NULL,
  created_at DATETIME(3) NOT NULL DEFAULT (UTC_TIMESTAMP(3)),
  updated_at DATETIME(3) NOT NULL DEFAULT (UTC_TIMESTAMP(3)),
  example_meaning VARCHAR(500) NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uk_words_wordbook_term (wordbook_id, term),
  CONSTRAINT fk_words_wordbook FOREIGN KEY (wordbook_id) REFERENCES wordbooks (id) ON DELETE CASCADE,
  CONSTRAINT ck_words_not_blank CHECK (CHAR_LENGTH(TRIM(term)) > 0 AND CHAR_LENGTH(TRIM(meaning)) > 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
```
> 주의: MySQL DDL 은 트랜잭션이 아니다. 2개 DROP 이 매우 단순하므로 중간 실패 위험은 낮지만, 실패 시 `SHOW TABLES` 로 상태를 확인한 뒤 이어서 처리한다.

## 4. 코드 변경 범위 (같은 커밋/브랜치에서 TDD 로)

| 파일 | 변경 |
| :--- | :--- |
| `src/backend/models/word.py`, `models/wordbook.py` | 삭제 |
| `src/backend/models/__init__.py` | `Word`, `Wordbook` import·`__all__` 제거 |
| `src/backend/tests/test_auth_api.py` | `Wordbook`/`Word` 사용 테스트(`test_signup_creates_no_personal_wordbooks_or_words`)를 "두 테이블이 없다"는 스키마 검사로 교체, import 정리 |
| `src/backend/tests/test_transition_schema.py` | `{"words","wordbooks"} <= tables` ("B-7 까지 보존") 단언을 `isdisjoint` 로 반전 |
| 신규 `src/backend/tests/test_drop_legacy_tables.py` | Red 우선: 메타데이터와 실제 DB 모두 `words`/`wordbooks` 부재를 확인 |
| 신규 alembic 리비전 | 3절 DDL |

회귀 방지: 새 테스트가 `Base.metadata.tables` 와 `information_schema` 양쪽에서 두 테이블이 없음을 검사하므로, 모델이 되살아나는 실수를 자동으로 잡는다.

## 5. 실행 순서 (승인 후)

1. 2절 백업 (a)(b) 실행 → 검증
2. Red: `test_drop_legacy_tables.py` 작성, 실패 확인
3. 모델 삭제 + 리비전 작성 + 테스트 수정
4. `alembic upgrade head` (사용자 승인 필요 항목) → `alembic downgrade -1` → `upgrade head` 왕복 확인
5. pytest 전체 + node 전체

## 6. 승인 요청

- [ ] 2절 백업 실행
- [ ] 3절 DDL 로 `alembic upgrade head` 실행
- [ ] 개발 DB 의 `wordbooks` 1건(테스트 계정 소유로 추정)은 이관 없이 삭제해도 되는지 확인
