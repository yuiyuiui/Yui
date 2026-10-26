# Complete source-application example

This neutral example is instruction data, not an exercise answer or an accepted
Audit A. It illustrates that a successful lookup must be registered as M, used
in a direct-input list and S, and instantiated through an application record.
The original equation a=b is an H node, not part of either point's type.

In a clean author stage, first call
`probe_library(id="M001", declaration="isCompact_singleton", module="Mathlib.Topology.Compactness.Compact")`.
Read the returned full signature and source. Its exact metadata/evidence are
bound by the controller; no source lookup or mathematical PASS is fabricated
by copying this example. The source has a topology condition and a point
parameter; its full claim is restated below. Exact mathematical fidelity and
application still require actual Audit A.

The clean tool binds omitted aliases, input/pin hashes, fixed language and
probed metadata. The resulting canonical files contain them in full.

```json
{
  "spec": {
    "format_version": 2,
    "case_id": "neutral-source-application",
    "full_target": "Let X be a topological space and a,b points of X. If a=b, then the singleton {b} is compact.",
    "conclusion": "T is compact.",
    "parameters": [
      {
        "symbol": "X",
        "type": "topological space"
      },
      {
        "symbol": "a",
        "type": "point of X"
      },
      {
        "symbol": "b",
        "type": "point of X"
      }
    ],
    "hypotheses": [
      {
        "id": "H001",
        "statement": "a=b.",
        "origin": "neutral-problem.txt:1"
      }
    ],
    "definitions": [
      {
        "id": "D001",
        "symbol": "S",
        "type": "subset of X",
        "definition": "S={a}, the set of points of X equal to a.",
        "depends_on": [],
        "requires": [],
        "binders": [],
        "objects": [
          "X",
          "a"
        ]
      },
      {
        "id": "D002",
        "symbol": "T",
        "type": "subset of X",
        "definition": "T={b}, the set of points of X equal to b.",
        "depends_on": [],
        "requires": [],
        "binders": [],
        "objects": [
          "X",
          "b"
        ]
      }
    ],
    "logic": {
      "classical": false,
      "rules": [
        "direct"
      ]
    },
    "pins": {},
    "inputs": []
  },
  "graph": {
    "format_version": 2,
    "case_id": "neutral-source-application",
    "propositions": [
      {
        "id": "H001",
        "kind": "hypothesis",
        "definitions": [],
        "binders": [],
        "objects": [
          "a",
          "b"
        ]
      },
      {
        "id": "M001",
        "kind": "mathlib",
        "statement": "For every topological space Y and every point z of Y, the singleton {z} is compact.",
        "definitions": [],
        "binders": [
          {
            "symbol": "Y",
            "type": "topological space"
          },
          {
            "symbol": "z",
            "type": "point of Y"
          }
        ],
        "objects": [
          "Y",
          "z"
        ],
        "source": {
          "declaration": "isCompact_singleton",
          "module": "Mathlib.Topology.Compactness.Compact",
          "hypotheses": [
            "The ambient type Y carries a topology."
          ]
        }
      },
      {
        "id": "N001",
        "kind": "internal",
        "statement": "S is compact.",
        "definitions": [
          "D001"
        ],
        "binders": [],
        "objects": [
          "S"
        ],
        "origin": "Instantiate the registered singleton theorem."
      },
      {
        "id": "P",
        "kind": "target",
        "definitions": [
          "D002"
        ],
        "binders": [],
        "objects": [
          "T"
        ]
      }
    ],
    "inferences": [
      {
        "id": "R001",
        "inputs": [
          "M001"
        ],
        "output": "N001",
        "definitions": [
          "D001"
        ],
        "rules": [
          "direct"
        ],
        "locals": [],
        "argument": [
          {
            "id": "S001",
            "text": "Instantiate M001 with Y=X and z=a. The parameter X supplies the topological structure, so the source gives compactness of {a}, which is S by its definition.",
            "uses": [
              "M001"
            ],
            "uses_local": [],
            "objects": [
              "X",
              "a",
              "S"
            ],
            "produces": [],
            "introduces": [],
            "discharges": []
          }
        ],
        "applications": [
          {
            "input": "M001",
            "at": "S001",
            "bindings": "Set Y=X with its declared topology and z=a.",
            "hypothesis_checks": [
              "X is declared as a topological space."
            ]
          }
        ]
      },
      {
        "id": "R002",
        "inputs": [
          "H001",
          "N001"
        ],
        "output": "P",
        "definitions": [
          "D001",
          "D002"
        ],
        "rules": [
          "direct"
        ],
        "locals": [],
        "argument": [
          {
            "id": "S001",
            "text": "H001 states a=b. Substitution into S={a} and T={b} yields S=T. N001 states that S is compact; equality substitution therefore gives compactness of T.",
            "uses": [
              "H001",
              "N001"
            ],
            "uses_local": [],
            "objects": [
              "a",
              "b",
              "S",
              "T"
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
