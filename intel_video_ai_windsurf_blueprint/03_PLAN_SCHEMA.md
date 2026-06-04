# JSON Plan Schema

The planner LLM must output an execution plan in JSON.

## Allowed Agents

```txt
transcription_agent
vision_agent
summary_agent
report_agent
clarification_agent
```

## Allowed Intents

```txt
TRANSCRIBE_VIDEO
SUMMARIZE_VIDEO
ANALYZE_OBJECTS
COUNT_OBJECTS
DETECT_GRAPHS
ANALYZE_OCR
SUMMARIZE_CHAT_HISTORY
GENERATE_PDF
GENERATE_PPTX
CLARIFY
```

## Schema

```json
{
  "confidence": 0.91,
  "steps": [
    {
      "step_id": "step_1",
      "intent": "COUNT_OBJECTS",
      "agent": "vision_agent",
      "inputs": {
        "target": "animals"
      },
      "depends_on": []
    },
    {
      "step_id": "step_2",
      "intent": "GENERATE_PDF",
      "agent": "report_agent",
      "inputs": {
        "title": "Animal Count Report",
        "source_step": "step_1"
      },
      "depends_on": ["step_1"]
    }
  ],
  "clarification_question": null
}
```

## Validation Rules

The validator must check:
- Valid JSON.
- Matches schema.
- `confidence >= 0.7`, unless intent is `CLARIFY`.
- Every agent is allowed.
- Every intent is allowed.
- Every `depends_on` references an existing previous step.
- No circular dependency.
- Video-required intents must have selected video.
- `CLARIFY` must include a clarification question.
- Report generation must have enough source data or previous step result.

## Examples

### Transcription

User:
```txt
Transcribe the video.
```

Plan:
```json
{
  "confidence": 0.95,
  "steps": [
    {
      "step_id": "step_1",
      "intent": "TRANSCRIBE_VIDEO",
      "agent": "transcription_agent",
      "inputs": {},
      "depends_on": []
    }
  ],
  "clarification_question": null
}
```

### Object Count + PDF

User:
```txt
How many animals are in the video? Export the answer as PDF.
```

Plan:
```json
{
  "confidence": 0.92,
  "steps": [
    {
      "step_id": "step_1",
      "intent": "COUNT_OBJECTS",
      "agent": "vision_agent",
      "inputs": {
        "target": "animals"
      },
      "depends_on": []
    },
    {
      "step_id": "step_2",
      "intent": "GENERATE_PDF",
      "agent": "report_agent",
      "inputs": {
        "title": "Animal Count Report",
        "source_step": "step_1"
      },
      "depends_on": ["step_1"]
    }
  ],
  "clarification_question": null
}
```

### Clarification

User:
```txt
Make a report.
```

Plan:
```json
{
  "confidence": 0.45,
  "steps": [
    {
      "step_id": "step_1",
      "intent": "CLARIFY",
      "agent": "clarification_agent",
      "inputs": {
        "question": "Do you want a PDF report or a PowerPoint presentation?"
      },
      "depends_on": []
    }
  ],
  "clarification_question": "Do you want a PDF report or a PowerPoint presentation?"
}
```
