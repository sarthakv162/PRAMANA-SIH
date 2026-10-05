"""Connect LMFE's token-enforcement API to current Transformers tokenizers.

LMFE 0.11's optional Transformers integration imports a tokenizer class from a
location removed in Transformers 5. Its public, framework-independent enforcer
works with both versions. This adapter follows the upstream tokenizer-decoding
algorithm without importing that obsolete integration module:
https://github.com/noamgat/lm-format-enforcer/blob/main/lmformatenforcer/integrations/transformers.py
"""

from typing import Any


def tokenizer_data(tokenizer: Any) -> Any:
    from lmformatenforcer import TokenEnforcerTokenizerData

    anchor = tokenizer.encode("0", add_special_tokens=False)[-1]
    prefix_length = len(tokenizer.decode([anchor]))
    special_ids = set(tokenizer.all_special_ids)
    tokens = []
    for token_id in range(len(tokenizer)):
        if token_id in special_ids:
            continue
        continuation = tokenizer.decode([anchor, token_id])[prefix_length:]
        standalone = tokenizer.decode([token_id])
        tokens.append((token_id, continuation, len(continuation) > len(standalone)))

    def decode(ids: list[int]) -> str:
        return str(tokenizer.decode(ids)).rstrip("\ufffd")

    return TokenEnforcerTokenizerData(tokens, decode, tokenizer.eos_token_id, False, len(tokenizer))


def schema_prefix(data: Any, schema: dict[str, Any]) -> Any:
    from lmformatenforcer import JsonSchemaParser, TokenEnforcer

    enforcer = TokenEnforcer(data, JsonSchemaParser(schema))

    def allowed_tokens(batch_id: int, token_ids: Any) -> list[int]:
        return list(enforcer.get_allowed_tokens(token_ids.tolist()).allowed_tokens)

    return allowed_tokens
