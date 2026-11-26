# 2026-11-26 - voda-voca - 모델과 DB 구조 비교(alembic check)에서 제외할 항목 (#38)
# 파일 위치: src/backend/db/schema_compare.py


def include_object(obj, name, type_, reflected, compare_to) -> bool:  # noqa: ANN001 (Alembic 훅 형식)
    """system_vocabularies.owner_id 의 외래키만 비교에서 뺀다.

    마이그레이션 0005 는 테이블 재작성을 피하려고 열 정의에 REFERENCES 를 붙여 추가했다. SQLite 는 이 외래키를
    강제하지만 SQLAlchemy 의 반영(reflection)은 열 정의에 붙은 외래키의 이름과 ON DELETE 를 읽지 못해 늘 차이로 본다.
    실제 제약은 test_migration_0005.py 가 PRAGMA foreign_key_list 로 확인한다.
    이 테이블을 batch 로 재작성하는 마이그레이션을 만들면 ON DELETE CASCADE 를 명시해 다시 걸어야 한다.
    """
    if type_ != "foreign_key_constraint" or obj.table.name != "system_vocabularies":
        return True
    return [column.name for column in obj.columns] != ["owner_id"]
