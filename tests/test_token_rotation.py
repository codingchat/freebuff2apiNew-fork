import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from freebuff2api.token_rotation import (
    RotationState,
    is_rate_limit_error,
    parse_429_info,
    read_current_token_num,
    write_current_token_num,
)

_429_MSG = (
    "Codebuff request failed: 429 "
    '{"error":"rate_limited","message":"Daily limit reached",'
    '"model":"deepseek/deepseek-v4-flash","limit":20,'
    '"retryAfterMs":3600000,"resetAt":"2026-08-02T00:00:00Z"}'
)


class Parse429Tests(unittest.TestCase):
    def test_is_rate_limit_error_detects_429(self) -> None:
        self.assertTrue(is_rate_limit_error(_429_MSG))
        self.assertFalse(is_rate_limit_error("Codebuff request failed: 500 boom"))
        self.assertFalse(is_rate_limit_error(""))

    def test_parse_429_info_extracts_fields(self) -> None:
        info = parse_429_info(_429_MSG)
        self.assertEqual(info["model"], "deepseek/deepseek-v4-flash")
        self.assertEqual(info["limit"], 20)
        self.assertEqual(info["retry_after_ms"], 3600000)
        self.assertEqual(info["retry_after_str"], "1小时0分钟")
        self.assertEqual(info["reset_at_sha"], "2026-08-02 08:00")

    def test_parse_429_info_handles_garbage(self) -> None:
        info = parse_429_info("no payload here")
        self.assertEqual(info["retry_after_ms"], 0)
        self.assertEqual(info["model"], "")


class CurrentTokenNumTests(unittest.TestCase):
    def test_write_then_read_roundtrip(self) -> None:
        with TemporaryDirectory() as tmp:
            env_path = Path(tmp) / ".env"
            write_current_token_num(env_path, 2)
            self.assertEqual(read_current_token_num(env_path), 2)

    def test_write_preserves_other_lines(self) -> None:
        with TemporaryDirectory() as tmp:
            env_path = Path(tmp) / ".env"
            env_path.write_text("FREEBUFF_TOKEN=abc\nexisting=1\n", encoding="utf-8")
            write_current_token_num(env_path, 1)
            lines = env_path.read_text(encoding="utf-8").splitlines()
            self.assertIn("FREEBUFF_TOKEN=abc", lines)
            self.assertIn("existing=1", lines)
            self.assertIn("CURRENT_TOKENNum=1", lines)

    def test_read_missing_file_returns_zero(self) -> None:
        with TemporaryDirectory() as tmp:
            self.assertEqual(read_current_token_num(Path(tmp) / "nope.env"), 0)


class RotationStateTests(unittest.TestCase):
    def _make(self, count: int, env_path: Path) -> RotationState:
        return RotationState(count, env_path)

    def test_initial_pointer_from_env(self) -> None:
        with TemporaryDirectory() as tmp:
            env_path = Path(tmp) / ".env"
            write_current_token_num(env_path, 1)
            state = self._make(3, env_path)
            self.assertEqual(state.current_index, 1)

    def test_next_index_skips_blocked(self) -> None:
        with TemporaryDirectory() as tmp:
            state = self._make(3, Path(tmp) / ".env")
            state.block(1, 30000)
            self.assertEqual(state.next_index(), 0)

    def test_next_index_skips_invalid(self) -> None:
        with TemporaryDirectory() as tmp:
            state = self._make(3, Path(tmp) / ".env")
            state.mark_invalid(0)
            self.assertEqual(state.next_index(), 1)

    def test_429_rotate_blocks_and_advances(self) -> None:
        with TemporaryDirectory() as tmp:
            state = self._make(3, Path(tmp) / ".env")
            index, _ = state.rotate(reason="429", error_message=_429_MSG, is_429=True, failed_index=0)
            self.assertEqual(index, 1)
            self.assertTrue(state.is_blocked(0))
            self.assertEqual(state.last_429_account, 0)
            self.assertEqual(state.last_429_info["retry_after_ms"], 3600000)

    def test_429_rotate_skips_other_blocked(self) -> None:
        with TemporaryDirectory() as tmp:
            state = self._make(3, Path(tmp) / ".env")
            state.block(1, 30000)  # next account also blocked
            index, _ = state.rotate(reason="429", error_message=_429_MSG, is_429=True, failed_index=0)
            self.assertEqual(index, 2)

    def test_all_blocked_picks_earliest_unblock(self) -> None:
        with TemporaryDirectory() as tmp:
            state = self._make(3, Path(tmp) / ".env")
            state.block(0, 120000)   # unblocks last
            state.block(1, 30000)    # unblocks first
            state.block(2, 60000)
            index, _ = state.rotate(reason="429", error_message=_429_MSG, is_429=True, failed_index=0)
            self.assertEqual(index, 1)

    def test_rotate_persists_pointer(self) -> None:
        with TemporaryDirectory() as tmp:
            env_path = Path(tmp) / ".env"
            state = self._make(3, env_path)
            state.rotate(reason="429", error_message=_429_MSG, is_429=True, failed_index=0)
            self.assertEqual(read_current_token_num(env_path), 1)

    def test_set_active_persists(self) -> None:
        with TemporaryDirectory() as tmp:
            env_path = Path(tmp) / ".env"
            state = self._make(3, env_path)
            state.set_active(2)
            self.assertEqual(state.current_index, 2)
            self.assertEqual(read_current_token_num(env_path), 2)

    def test_non_429_rotate_is_debounced(self) -> None:
        with TemporaryDirectory() as tmp:
            state = self._make(3, Path(tmp) / ".env")
            state.rotate(reason="manual")
            # second manual rotate within 30s should be a no-op
            index, _ = state.rotate(reason="manual")
            self.assertEqual(index, 1)

    def test_record_failure_marks_invalid_after_threshold(self) -> None:
        with TemporaryDirectory() as tmp:
            state = self._make(1, Path(tmp) / ".env")
            state.record_failure(0)
            state.record_failure(0)
            self.assertEqual(state.status_of(0), "active")
            state.record_failure(0)
            self.assertEqual(state.status_of(0), "invalid")

    def test_status_rows_shape(self) -> None:
        with TemporaryDirectory() as tmp:
            state = self._make(2, Path(tmp) / ".env")
            state.block(0, 30000)
            rows = state.status_rows()
            self.assertEqual(len(rows), 2)
            self.assertTrue(rows[0]["blocked"])
            self.assertGreater(rows[0]["block_remaining"], 0)
            self.assertTrue(rows[0]["is_current"])

    def test_all_blocked_property(self) -> None:
        with TemporaryDirectory() as tmp:
            state = self._make(2, Path(tmp) / ".env")
            state.block(0, 30000)
            state.block(1, 30000)
            self.assertTrue(state.all_blocked)
            self.assertEqual(state.available_count, 0)

    # ── Per-model cooldown ─────────────────────────

    def test_block_only_cools_given_model(self) -> None:
        with TemporaryDirectory() as tmp:
            state = self._make(2, Path(tmp) / ".env")
            state.block(0, 60000, model="deepseek/deepseek-v4-pro")
            # The blocked model is unavailable on account 1...
            self.assertTrue(state.is_blocked(0, "deepseek/deepseek-v4-pro"))
            # ...but other models on the same account remain usable
            self.assertFalse(state.is_blocked(0, "deepseek/deepseek-v4-flash"))
            # Account-level view still reports blocked (any model)
            self.assertTrue(state.is_blocked(0))
            self.assertEqual(state.available_count, 1)
            self.assertEqual(state.available_count_for("deepseek/deepseek-v4-flash"), 2)
            self.assertEqual(state.available_count_for("deepseek/deepseek-v4-pro"), 1)

    def test_429_rotate_with_model_cooldown_skips_only_that_model(self) -> None:
        with TemporaryDirectory() as tmp:
            state = self._make(3, Path(tmp) / ".env")
            idx, _ = state.rotate(
                reason="429",
                error_message=_429_MSG,  # carries model deepseek/deepseek-v4-flash
                is_429=True,
                failed_index=0,
                model="deepseek/deepseek-v4-flash",
            )
            self.assertEqual(idx, 1)
            # Account 1 is blocked only for the flash model
            self.assertTrue(state.is_blocked(0, "deepseek/deepseek-v4-flash"))
            self.assertFalse(state.is_blocked(0, "moonshotai/kimi-k2.6"))
            # next_index skips the blocked model but can still pick account 1 for others
            self.assertEqual(state.next_index(0, model="moonshotai/kimi-k2.6"), 0)
            self.assertEqual(state.next_index(model="moonshotai/kimi-k2.6"), 1)
            self.assertEqual(state.next_index(model="deepseek/deepseek-v4-flash"), 1)

    def test_mark_success_resets_failures(self) -> None:
        with TemporaryDirectory() as tmp:
            state = self._make(1, Path(tmp) / ".env")
            state.record_failure(0)
            state.record_failure(0)
            self.assertEqual(state.failure_count_of(0), 2)
            state.mark_success(0)
            self.assertEqual(state.failure_count_of(0), 0)

    def test_model_availability_matrix_shape(self) -> None:
        with TemporaryDirectory() as tmp:
            state = self._make(2, Path(tmp) / ".env")
            state.block(0, 60000, model="deepseek/deepseek-v4-pro")
            rows = state.model_availability(
                ["deepseek/deepseek-v4-flash", "deepseek/deepseek-v4-pro"]
            )
            self.assertEqual(len(rows), 2)
            flash_row = rows[0]
            self.assertEqual(flash_row["model"], "deepseek/deepseek-v4-flash")
            self.assertEqual(len(flash_row["accounts"]), 2)
            # account 1 flash: active
            self.assertEqual(flash_row["accounts"][0]["status"], "active")
            # account 1 pro: blocked with remaining > 0
            pro_row = rows[1]
            self.assertEqual(pro_row["accounts"][0]["status"], "blocked")
            self.assertGreater(pro_row["accounts"][0]["block_remaining"], 0)


if __name__ == "__main__":
    unittest.main()
