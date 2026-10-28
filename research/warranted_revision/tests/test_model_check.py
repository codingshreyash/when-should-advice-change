"""model_check's template checks, with stub tokenizers for the two system-prompt placements."""

from warranted_revision import goal_screen as gs
from warranted_revision import model_check as mc
from warranted_revision.runner import PKG_ROOT


class Tok:
    """Renders like a chat template: system first (Qwen style) or before the last user turn
    (Mistral style); ``drop_system`` and ``raises`` simulate broken templates."""

    def __init__(
        self, style="first", drop_system=False, raises=False, strip=False, drop_assistant=False
    ):
        self.style, self.drop, self.raises = style, drop_system, raises
        self.strip, self.drop_assistant = strip, drop_assistant

    def apply_chat_template(self, msgs, tokenize, add_generation_prompt, **kw):
        if self.raises:
            raise ValueError("Conversation roles must alternate")
        sys_msg, turns = msgs[0]["content"], msgs[1:]
        last_user = max(i for i, m in enumerate(turns) if m["role"] == "user")
        out = "" if self.drop or self.style != "first" else f"<s>{sys_msg}</s>"
        for i, m in enumerate(turns):
            if m["role"] == "assistant" and self.drop_assistant:
                continue
            body = m["content"].strip() if self.strip else m["content"]
            m = {**m, "content": body}
            pre = (
                f"{sys_msg}\n\n"
                if self.style == "last" and i == last_user and not self.drop
                else ""
            )
            out += f"<{m['role']}>{pre}{m['content']}</{m['role']}>"
        return out + "<assistant>"

    def __call__(self, text, add_special_tokens=False):
        return {"input_ids": text.split()}


def _cfg():
    return gs.load_config(PKG_ROOT / "configs/goal_screen_qwen.json")


def test_both_placements_pass_and_are_recorded():
    a = mc.check_template(Tok("first"), _cfg(), {})
    b = mc.check_template(Tok("last"), _cfg(), {})
    assert not a["problems"] and not b["problems"]
    assert a["shapes"]["decision"]["system_position"] == "before_first_user"
    assert b["shapes"]["decision"]["system_position"] == "before_last_user"
    assert b["shapes"]["first"]["system_position"] == "before_first_user"
    assert a["longest_prompt_tokens"] > 0


def test_dropped_system_prompt_and_raising_template_fail():
    assert any(
        "system prompt appears 0x" in p
        for p in mc.check_template(Tok(drop_system=True), _cfg(), {})["problems"]
    )
    assert any(
        "template raised" in p for p in mc.check_template(Tok(raises=True), _cfg(), {})["problems"]
    )


def test_memory_estimate():
    class C:
        num_hidden_layers, num_key_value_heads, num_attention_heads = 40, 8, 32
        head_dim, hidden_size, max_position_embeddings = 128, 5120, 131072

    m = mc.memory(
        C(), 12_247_782_400, gs.load_config(PKG_ROOT / "configs/goal_screen_qwen.json"), 2500
    )
    assert m["weights_gb_bf16"] == 24.5 and m["fits"] is True


def test_whitespace_stripping_passes_but_a_dropped_turn_fails():
    stripped = Tok(strip=True)
    cfg = _cfg()
    msgs = mc.protocol_messages(cfg)
    msgs["free"][1]["content"] += "  \n"  # a reply with trailing whitespace
    assert not mc.check_template(stripped, cfg, {})["problems"]
    probs = mc.check_template(Tok(drop_assistant=True), cfg, {})["problems"]
    assert any("(assistant) absent" in p for p in probs)
