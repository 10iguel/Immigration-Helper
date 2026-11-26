"""Form reviews (uploaded_form) and the issues found (form_issue) in PostgreSQL. The forms themselves aren't stored."""
from immigration_helper.models import FormId
from immigration_helper.review import Issue, Review, ReviewSummary, Severity
from immigration_helper.storage.database import Database

_SUMMARY_SQL = (
    "SELECT u.upload_id, u.form_id, u.original_filename, u.uploaded_at, "
    "count(*) FILTER (WHERE i.severity = 'error') AS errors, "
    "count(*) FILTER (WHERE i.severity = 'warning') AS warnings "
    "FROM uploaded_form u LEFT JOIN form_issue i ON i.upload_id = u.upload_id "
)


class PostgresReviewStore:
    def __init__(self, database: Database):
        self._database = database

    def save(self, user_id: int, form: FormId, filename: str, issues: list[Issue]) -> ReviewSummary:
        with self._database.connect() as connection:
            row = connection.execute(
                "INSERT INTO uploaded_form (user_id, form_id, original_filename) VALUES (%s, %s, %s) "
                "RETURNING upload_id, uploaded_at",
                (user_id, form.value, filename),
            ).fetchone()
            with connection.cursor() as cursor:
                cursor.executemany(
                    "INSERT INTO form_issue (upload_id, severity, location, message, instruction_label) "
                    "VALUES (%s, %s, %s, %s, %s)",
                    [(row["upload_id"], issue.severity.value, issue.location, issue.message, issue.instruction_label)
                     for issue in issues],
                )
        errors = sum(1 for issue in issues if issue.severity is Severity.ERROR)
        return ReviewSummary(row["upload_id"], form, filename, row["uploaded_at"], errors, len(issues) - errors)

    def list_for(self, user_id: int) -> list[ReviewSummary]:
        with self._database.connect() as connection:
            rows = connection.execute(
                _SUMMARY_SQL + "WHERE u.user_id = %s GROUP BY u.upload_id ORDER BY u.uploaded_at DESC, u.upload_id DESC",
                (user_id,),
            ).fetchall()
        return [_summary(row) for row in rows]

    def load(self, user_id: int, review_id: int) -> Review | None:
        with self._database.connect() as connection:
            row = connection.execute(
                _SUMMARY_SQL + "WHERE u.upload_id = %s AND u.user_id = %s GROUP BY u.upload_id", (review_id, user_id)
            ).fetchone()
            if row is None:
                return None
            issues = connection.execute(
                "SELECT severity, location, message, instruction_label FROM form_issue WHERE upload_id = %s "
                "ORDER BY issue_id",
                (review_id,),
            ).fetchall()
        return Review(_summary(row), tuple(
            Issue(Severity(issue["severity"]), issue["location"], issue["message"], issue["instruction_label"])
            for issue in issues
        ))

    def delete(self, user_id: int, review_id: int) -> bool:
        with self._database.connect() as connection:
            deleted = connection.execute(
                "DELETE FROM uploaded_form WHERE upload_id = %s AND user_id = %s", (review_id, user_id)
            ).rowcount
        return deleted == 1


def _summary(row: dict) -> ReviewSummary:
    return ReviewSummary(row["upload_id"], FormId(row["form_id"]), row["original_filename"], row["uploaded_at"],
                         row["errors"], row["warnings"])
