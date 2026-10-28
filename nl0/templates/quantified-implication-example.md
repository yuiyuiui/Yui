# Neutral quantified implication example

This is a complete format example, not a test solution or an Audit A receipt.
The target has no original hypotheses. The antecedent r=0 belongs under a new
universal binder, so it is a temporary L1 inside R001, not a new H root and not
a property granted by the ambient type of r. F001 remains under L1; F002 is
the complete implication after discharge. Neither an unconditional r*r=0 nor
a conclusion about one unspecified r can replace the quantified target.

```json
{
  "spec": {
    "format_version": 2,
    "case_id": "neutral-quantified-implication",
    "full_target": "For every real number r, r=0 implies r*r=0.",
    "conclusion": "For every real number r, r=0 implies r*r=0.",
    "parameters": [],
    "hypotheses": [],
    "definitions": [],
    "logic": {
      "classical": false,
      "rules": [
        "direct",
        "implication_introduction",
        "forall_introduction"
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
    "case_id": "neutral-quantified-implication",
    "spec_sha256": "controller-bound",
    "propositions": [
      {
        "id": "P",
        "kind": "target",
        "statement": "For every real number r, r=0 implies r*r=0.",
        "definitions": [],
        "binders": [
          {
            "symbol": "r",
            "type": "real number"
          }
        ],
        "objects": [
          "r",
          "0"
        ]
      }
    ],
    "inferences": [
      {
        "id": "R001",
        "inputs": [],
        "output": "P",
        "definitions": [],
        "rules": [
          "direct",
          "implication_introduction",
          "forall_introduction"
        ],
        "locals": [
          {
            "symbol": "r",
            "type": "real number",
            "scope": "R001/argument",
            "start": "S001",
            "end": "S003",
            "kind": "arbitrary",
            "declaration": "Fix an arbitrary real number r.",
            "from_inputs": [],
            "from_local": [],
            "objects": []
          }
        ],
        "argument": [
          {
            "id": "S001",
            "text": "Fix an arbitrary real number r. Temporarily assume L1: r=0. Record F001: r=0.",
            "uses": [],
            "uses_local": [],
            "objects": [
              "r",
              "0"
            ],
            "produces": [
              {
                "id": "F001",
                "statement": "r=0.",
                "binders": [],
                "objects": [
                  "r",
                  "0"
                ],
                "assumptions": [
                  "L1"
                ]
              }
            ],
            "introduces": [
              "L1"
            ],
            "discharges": []
          },
          {
            "id": "S002",
            "text": "Under L1, F001 gives r=0. Substitution in r*r gives 0*0=0 by the zero law. Discharge L1 by implication introduction: if r=0 then r*r=0. This full implication is F002.",
            "uses": [],
            "uses_local": [
              "F001"
            ],
            "objects": [
              "r",
              "0"
            ],
            "produces": [
              {
                "id": "F002",
                "statement": "If r=0 then r*r=0.",
                "binders": [],
                "objects": [
                  "r",
                  "0"
                ],
                "assumptions": []
              }
            ],
            "introduces": [],
            "discharges": [
              "L1"
            ]
          },
          {
            "id": "S003",
            "text": "F002 holds for the arbitrary r, and no local assumption remains. Universal introduction therefore proves: for every real number r, r=0 implies r*r=0.",
            "uses": [],
            "uses_local": [
              "F002"
            ],
            "objects": [
              "r",
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

The fixed finite algebra justifies the zero law; no analysis/linear-algebra theorem
is granted. This demonstrates binder/assumption accounting only. Independent
Audit A still checks the actual mathematics, declarations and complete output.
