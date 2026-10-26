# Neutral guarded-definition example

This template implements the existing Audit A definitions/structure requirements.
It is unrelated to any exercise. The first inference proves unique existence
without using the not-yet-constructed w. The D002 record can occur in the global
specification, but its requires field prevents using w until N001 is supplied.
The second inference receives N001 and proves the full target, including the
existence clause and the value of w. Textual file order is not proof order.

Moving w into an unproved restricted domain or using it inside R001 would not
solve its guard. The latter creates a circular construction obligation. The
example uses only explicit definitions, equality and ordinary logic. Its JSON
is tested structurally; this file is not an Audit A receipt. Controller-owned
metadata placeholders are bound by the ordinary author adapter.

```json
{
  "spec": {
    "format_version": 2,
    "case_id": "neutral-guarded-definition",
    "full_target": "For any real a define Q(r) to mean r=a. Prove unique existence, then denote its unique witness by w and prove w=a.",
    "conclusion": "There exists a unique real r such that Q(r), and w=a.",
    "parameters": [
      {
        "symbol": "a",
        "type": "real number"
      }
    ],
    "hypotheses": [],
    "definitions": [
      {
        "id": "D001",
        "symbol": "Q",
        "type": "predicate on real numbers",
        "definition": "For every real r, Q(r) holds if and only if r=a.",
        "depends_on": [],
        "requires": [],
        "binders": [
          {
            "symbol": "r",
            "type": "real number"
          }
        ],
        "objects": [
          "r",
          "a"
        ]
      },
      {
        "id": "D002",
        "symbol": "w",
        "type": "real number",
        "definition": "w is the unique real r satisfying Q(r).",
        "depends_on": [
          "D001"
        ],
        "requires": [
          "N001"
        ],
        "binders": [
          {
            "symbol": "r",
            "type": "real number"
          }
        ],
        "objects": [
          "Q",
          "r"
        ]
      }
    ],
    "logic": {
      "classical": true,
      "rules": [
        "direct",
        "forall_introduction",
        "exists_elimination"
      ]
    },
    "pins": {},
    "inputs": []
  },
  "graph": {
    "format_version": 2,
    "case_id": "neutral-guarded-definition",
    "spec_sha256": "controller-bound",
    "propositions": [
      {
        "id": "N001",
        "kind": "internal",
        "statement": "There exists a unique real r such that Q(r).",
        "definitions": [
          "D001"
        ],
        "binders": [
          {
            "symbol": "r",
            "type": "real number"
          }
        ],
        "objects": [
          "Q",
          "r"
        ],
        "origin": "Construction guard proved before using the uniquely selected object."
      },
      {
        "id": "P",
        "kind": "target",
        "statement": "There exists a unique real r such that Q(r), and w=a.",
        "definitions": [
          "D001",
          "D002"
        ],
        "binders": [
          {
            "symbol": "r",
            "type": "real number"
          }
        ],
        "objects": [
          "Q",
          "r",
          "w",
          "a"
        ]
      }
    ],
    "inferences": [
      {
        "id": "R001",
        "inputs": [],
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
            "text": "Substituting a into the supplied definition of Q gives Q(a) if and only if a=a. Equality reflexivity proves Q(a). Unfolding that same definition also gives forall real r, Q(r) implies r=a. Thus a is a witness and every witness equals a, which proves existence and uniqueness.",
            "uses": [],
            "uses_local": [],
            "objects": [
              "a",
              "Q"
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
            "text": "N001 supplies the established unique existence required to use w. By its guarded definition, w is that unique witness and satisfies Q(w). Unfolding Q gives w=a. Conjoining this equality with the unique existence in N001 proves the complete output.",
            "uses": [
              "N001"
            ],
            "uses_local": [],
            "objects": [
              "a",
              "Q",
              "w"
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
