# Development data boundary

Moving the working repository out of OneDrive reduces accidental cloud
synchronization. It does **not** make the repository an approved storage location
for protected health information, personally identifiable information,
controlled military information, or real participant research records.

For the development/hackathon phase, use only:

- Public reference information with recorded provenance.
- Synthetic service-member records explicitly labeled synthetic, if separately
  authorized. A schema supporting synthetic data is not approval to generate careers.
- Explicitly fictional demonstration and unit-test records.

Do not store actual medical records, SSNs, DoD IDs, EDIPI values, participant
names, addresses, exact birth dates, or similar identifiers. Do not place such
information in notes, test fixtures, notebook outputs, logs or Git history.
Public-source author/organization attribution is bibliographic metadata, not
participant data.

Anonymous IDs alone do not guarantee anonymity: detailed career histories can
identify people. Git ignore rules are convenience controls, not security.
No encryption, compliance architecture, access-control system or clinical
workflow is implemented in this phase. Future participant research needs a
separate governance and approved-storage decision.

No training-frequency modeling, synthetic career generation, ML, NLP extraction,
RAG, UI, symptom/exposure correlation or blast-risk scoring is authorized by the
reference dataset work.
