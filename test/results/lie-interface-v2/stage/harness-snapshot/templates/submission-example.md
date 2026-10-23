# Complete NL0 v2 submission example

This is a neutral format example, not a reference solution to any exercise or
an accepted Audit A. It is available through `read_yui`; test fixtures and old
proofs remain inaccessible. Copy the data shape, not its mathematical contents.
The clean NL0 tool binds `inputs`, `pins` and `spec_sha256` before checking.
Every other field is authored and reviewed. Empty arrays are intentional.
The clean tool also permits omitting redundant H/P statements and E/M
`source.statement`: it copies their primary spec/proposition statement.
Conflicting supplied duplicates are rejected. The canonical files always
contain the complete texts, and source fidelity still needs actual review.

```json
{
  "spec": {
    "format_version": 2,
    "case_id": "closed-addition-format-example",
    "full_target": "For natural numbers a and b, if a=b, then a+0=b.",
    "conclusion": "a+0=b.",
    "parameters": [
      {
        "symbol": "a",
        "type": "natural number"
      },
      {
        "symbol": "b",
        "type": "natural number"
      }
    ],
    "hypotheses": [
      {
        "id": "H001",
        "statement": "a=b.",
        "origin": "problem.txt:1"
      }
    ],
    "definitions": [],
    "logic": {
      "classical": false,
      "rules": [
        "direct"
      ],
      "calculations": [
        "Equality symmetry, substitution, and the natural-number additive identity a+0=a."
      ],
      "primitives": [
        {
          "symbol": "0",
          "type": "natural number",
          "meaning": "The additive identity of natural numbers."
        }
      ]
    },
    "pins": {
      "lean_version": "controller-bound",
      "mathlib_commit": "controller-bound",
      "mathlib_root": "controller-bound"
    },
    "inputs": []
  },
  "graph": {
    "format_version": 2,
    "case_id": "closed-addition-format-example",
    "spec_sha256": "controller-bound",
    "propositions": [
      {
        "id": "H001",
        "kind": "hypothesis",
        "statement": "a=b.",
        "definitions": [],
        "binders": [],
        "objects": [
          "a",
          "b"
        ]
      },
      {
        "id": "N001",
        "kind": "internal",
        "statement": "b=a.",
        "definitions": [],
        "binders": [],
        "objects": [
          "a",
          "b"
        ],
        "origin": "Equality symmetry applied to the original hypothesis."
      },
      {
        "id": "P",
        "kind": "target",
        "statement": "a+0=b.",
        "definitions": [],
        "binders": [],
        "objects": [
          "a",
          "b",
          "0"
        ]
      }
    ],
    "inferences": [
      {
        "id": "R001",
        "inputs": [
          "H001"
        ],
        "output": "N001",
        "definitions": [],
        "rules": [
          "direct"
        ],
        "locals": [],
        "argument": [
          {
            "id": "S001",
            "text": "H001 gives a=b. Equality symmetry gives b=a.",
            "uses": [
              "H001"
            ],
            "uses_local": [],
            "objects": [
              "a",
              "b"
            ],
            "produces": [],
            "introduces": [],
            "discharges": []
          }
        ],
        "applications": []
      },
      {
        "id": "R002",
        "inputs": [
          "N001"
        ],
        "output": "P",
        "definitions": [],
        "rules": [
          "direct"
        ],
        "locals": [
          {
            "symbol": "c",
            "type": "natural number",
            "scope": "R002/argument",
            "start": "S001",
            "end": "S002",
            "kind": "definition",
            "declaration": "Define c=a+0.",
            "from_inputs": [],
            "from_local": [],
            "objects": [
              "a",
              "0"
            ]
          }
        ],
        "argument": [
          {
            "id": "S001",
            "text": "Define c=a+0. The declared additive identity a+0=a yields c=a.",
            "uses": [],
            "uses_local": [],
            "objects": [
              "a",
              "c",
              "0"
            ],
            "produces": [
              {
                "id": "F001",
                "statement": "c=a.",
                "objects": [
                  "a",
                  "c"
                ],
                "assumptions": [],
                "binders": []
              }
            ],
            "introduces": [],
            "discharges": []
          },
          {
            "id": "S002",
            "text": "N001 gives b=a; equality symmetry gives a=b. F001 gives c=a, hence c=b by substitution. Substituting the definition c=a+0 yields a+0=b.",
            "uses": [
              "N001"
            ],
            "uses_local": [
              "F001"
            ],
            "objects": [
              "a",
              "b",
              "c",
              "0"
            ],
            "produces": [],
            "introduces": [],
            "discharges": []
          }
        ],
        "applications": []
      }
    ]
  }
}
```

## Local existence before choice

A `definition` introduces an explicitly given expression; an `arbitrary` local
is universally fixed. Neither silently grants an existence theorem. A `witness`
requires a direct input or a prior local F establishing its existence.

For example, after an actual argument has proved `exists b, Q(b)` as F001 in
S001, a witness introduced at S002 records `kind: "witness"`, `start: "S002"`,
`end` at its last use, `from_local: ["F001"]`, and a declaration specifying the
chosen witness and its property. Its type/declaration objects must already be
available at S002. Use F001 in the argument's `uses_local`; never cite the
newly produced F001 as an earlier fact inside S001 itself. Every object used
in text needs its legitimate declaration, even if omitted from an inventory.
These fields account for a mathematical argument; they do not prove Q.

A structural rejection is ordinary format feedback. Repair it using the
contract and this example. It is not, by itself, a mathematical gap, missing
source, or new attempt limit. Preserve actual mathematical/source obstacles
separately and retain rejected candidates.
