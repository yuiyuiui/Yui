"""Read the one shared NL0 acceptance authority from Audit A; no judgments."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re

SOURCE = Path(__file__).resolve().parents[1]/'references/audit-a.md'
BEGIN = '<!-- yui-nl0-acceptance:begin -->'
END = '<!-- yui-nl0-acceptance:end -->'


class AcceptanceContract:
    def __init__(self, text):
        if text.count(BEGIN)!=1 or text.count(END)!=1 or text.index(BEGIN)>=text.index(END):
            raise ValueError('ACCEPTANCE_AUTHORITY: Audit A must contain one complete shared section')
        self.section=text.split(BEGIN,1)[1].split(END,1)[0].strip()
        versions=re.findall(r'^Contract version: `([^`]+)`\.$',self.section,re.M)
        if len(versions)!=1:raise ValueError('ACCEPTANCE_AUTHORITY: one explicit contract version required')
        self.version=versions[0]
        self.rows={}
        for line in self.section.splitlines():
            if not line.startswith('| `'):continue
            parts=[p.strip() for p in line.strip('|').split('|')]
            if len(parts)!=4 or not re.fullmatch(r'`[a-z_]+`',parts[0]):
                raise ValueError('ACCEPTANCE_AUTHORITY: malformed requirement row')
            identity=parts[0][1:-1]
            if identity in self.rows or parts[1] not in {'package','closure','inference'} or not parts[3]:
                raise ValueError('ACCEPTANCE_AUTHORITY: duplicate ID, missing requirement or invalid review group')
            if parts[2] not in {'original_context_note','output_notes','declaration_check',
                                'dependency_and_local_assumption_check','source_application_check'}:
                raise ValueError('ACCEPTANCE_AUTHORITY: unknown author evidence group')
            self.rows[identity]={'review_group':parts[1],'author_group':parts[2],'requirement':parts[3]}
        if not self.rows or any(not self.check_ids(g) for g in ['package','closure','inference']):
            raise ValueError('ACCEPTANCE_AUTHORITY: package, closure and inference requirements are required')
        self.document_sha256=hashlib.sha256(text.encode()).hexdigest()
        self.section_sha256=hashlib.sha256(self.section.encode()).hexdigest()

    def check_ids(self, group):
        return {key for key,row in self.rows.items() if row['review_group']==group}

    def author_groups(self):
        return {group:sorted(key for key,row in self.rows.items() if row['author_group']==group)
                for group in sorted({row['author_group'] for row in self.rows.values()})}

    def metadata(self):
        return {'source':'references/audit-a.md','version':self.version,
                'section_sha256':self.section_sha256,'document_sha256':self.document_sha256,
                'criterion_ids':sorted(self.rows)}

    def instructions(self):
        return ('Shared NL0 acceptance authority (same frozen section for author and Audit A):\n'+
                json.dumps(self.metadata(),sort_keys=True)+'\n'+self.section)


def current():
    return AcceptanceContract(SOURCE.read_text())
