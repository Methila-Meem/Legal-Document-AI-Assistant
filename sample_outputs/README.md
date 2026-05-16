# Sample Outputs

These files are synthetic examples that show the type of output the application
can produce while processing the sample inputs. They are provided only to help
reviewers quickly understand system behavior. They are not formal assessment
results and do not claim measured performance.

Files:

- `extracted_text_example.json` - example processed text output for
  `sample_notice.txt`.
- `structured_fields_example.json` - example parties, dates, addresses,
  monetary amounts, case number, key events, and unclear items.
- `retrieval_evidence_example.json` - example retrieved chunks with page/source
  metadata and relevance scores.
- `generated_draft_example.md` - example grounded first-pass case fact summary.
- `operator_edit_example.json` - example edited draft content and operator
  intent.
- `learned_rules_example.json` - example reusable rules extracted from the
  operator edit.
- `improved_draft_example.md` - example improved draft that applies the learned
  rules.

Suggested review order:

1. Compare `generated_draft_example.md` with `operator_edit_example.json`.
2. Review the reusable preferences in `learned_rules_example.json`.
3. Compare `generated_draft_example.md` with `improved_draft_example.md` to see
   how cautious wording and document-purpose context can be reflected.
