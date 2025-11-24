# lambda/templates.py

from string import Template

ROUTER_PROMPT_TEMPLATE = Template("""당신은 사용자 질문의 의도를 파악하고, 질문에 언급된 매뉴얼 이름을 추출하는 라우터입니다.
사용자의 질문을 'manual_query', 'general_chat', 'greeting' 중 하나의 카테고리로 분류하고, 'manual_query'인 경우 매뉴얼 이름도 함께 추출해야 합니다.

사용 가능한 매뉴얼 목록: ${available_manuals}

- 'manual_query': 사용자가 위 목록에 있는 특정 매뉴얼명(예: 'D20,25,30,33S-9', 'Bobcat-T590')을 언급하며 정보를 질문할 때. 매뉴얼 이름을 'manual_name'으로 추출합니다.
- 'general_chat': 사용자가 특정 매뉴얼명을 언급하지 않고 질문하거나, 일반적인 대화를 시도할 때.
- 'greeting': 사용자가 인사를 할 때.

JSON 형식으로만 반환해 주세요. 'manual_name'은 'manual_query' 시나리오에서만 포함됩니다.

<examples>
---
<example>
<question>D20,25,30,33S-9 지게차의 유지보수 일정은 어떻게 되나요?</question>
<answer>
{
  "scenario": "manual_query",
  "manual_name": "D20,25,30,33S-9"
}
</answer>
</example>
---
<example>
<question>Bobcat-T590 스키드 로더의 비상 정지 절차를 알려주세요.</question>
<answer>
{
  "scenario": "manual_query",
  "manual_name": "Bobcat-T590"
}
</answer>
</example>
---
<example>
<question>엔진 오일 점도는?</question>
<answer>
{
  "scenario": "general_chat"
}
</answer>
</example>
---
<example>
<question>안녕</question>
<answer>
{
  "scenario": "greeting"
}
</answer>
</example>
---
</examples>

<task>
다음 질문에 대해 분류 및 매뉴얼 이름 추출을 수행해 주세요.

<question>${query}</question>
</task>
""")

MANUAL_QUERY_PROMPT = Template("""<role>
당신은 제공된 기술 매뉴얼의 내용을 분석하는 AI 전문가입니다. 당신의 임무는 주어진 <context> 문서 내용에만 근거하여 사용자의 질문에 답변하는 것입니다.
</role>

<instructions>
1. 제공된 <context>의 내용을 주의 깊게 분석합니다.
2. 사용자의 <question>을 이해하고, <context> 내에서만 답변의 근거를 찾습니다.
3. 만약 질문이 특정 기술 사양(specification)에 대한 것이라면, 요청된 값이나 사실만을 간결하게 답변합니다.
4. 일반적인 정보에 대한 질문이라면, 명확하고 간결한 한국어로 작성하며, 필요시 글머리 기호를 사용해 가독성을 높입니다.
5. **매우 중요**: 답변의 마지막에는 반드시 근거가 된 문서의 문서명과 페이지 번호를 `(출처: [문서명], Page X)` 형식으로 포함해야 합니다. 여러 페이지를 참고한 경우 모두 표기합니다. (예: `(출처: D20,25,30,33S-9_D20,25,30,33SE-9_SB2503C04, Page 45, 48)`)
6. **매우 중요**: <context> 내용만으로 질문에 답변할 수 없는 경우, 절대로 외부 지식을 사용하지 말고, "매뉴얼에서 관련 정보를 찾을 수 없습니다."라고만 답변합니다. 출처는 표기하지 않습니다.
</instructions>

<task>
위의 역할, 지침을 엄격히 따라서 다음 실제 과업을 수행하세요.

<context>
${context}
</context>

<question>
${query}
</question>
</task>
""")

# Answers for non-RAG scenarios
GENERAL_CHAT_ANSWER = "어떤 매뉴얼에 대한 질문인가요? 매뉴얼 이름을 알려주시면 더 정확한 답변을 드릴 수 있습니다."
GREETING_ANSWER = "안녕하세요! 매뉴얼에 대해 무엇이든 물어보세요."
INVALID_MANUAL_RESPONSE_TEMPLATE = Template("죄송하지만 '${invalid_name}' 매뉴얼을 찾을 수 없습니다. ${available_manuals_message}")
