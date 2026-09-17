# Source review and local downloads

The versioned, typed source registry is `data/reference/sources.json`. Each fact
in a reference dataset links to this registry with a page/section locator. Source
versions, UTC access dates, original-byte hashes where available and retrieval
limitations are recorded rather than silently filling unknown metadata.

`downloads/` holds local public-source originals and temporary review renders or
text extractions. These are ignored by Git. Six original documents/pages were
successfully downloaded for V0.1; other official pages were reviewed through
indexed source text and have no claimed original-byte hash. Download failures
are documented in the registry and research review, not replaced with secondary
blogs, social media or unsourced summaries.

Do not commit long copied passages, participant records, controlled material or
licensed source documents without checking redistribution rights. Human review
must confirm that the exact cited passage supports each factual assertion. A
valid URL or an official organization name does not perform that review.

For future experiments, preserve permitted source originals in an approved
versioned archive alongside their hashes. Mutable URLs alone cannot guarantee
reproduction. See `data/reference/README.md` for release and validation procedures.
