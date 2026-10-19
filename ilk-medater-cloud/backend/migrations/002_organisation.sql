-- Organigramme validé (codes stables repris de ILK_GROUP_Organigramme_CRM_V0.7, complétés).
-- floor : 0 = RDC (Direction générale + services communs), 1 = R+1 (eurl medater), 2 = R+2 (cabinet ILK)
-- modules : périmètre fonctionnel couvert par une autorisation « département ».

INSERT INTO companies (code, name, legal_name) VALUES
 ('CONST', 'eurl medater', 'EURL MEDATER'),
 ('ARCH',  'cabinet ILK',  'Cabinet ILK');

INSERT INTO org_units (code, parent_code, company_code, name, kind, floor, modules, sort) VALUES
 ('GROUP', NULL, 'GROUP', 'ilk.medater groupe', 'group', 0, '{}', 0),

 -- Services communs (RDC)
 ('SHARED-EXEC',  'GROUP', 'GROUP', 'Direction générale',              'shared_service', 0, '{crm,projects,sites,studies,documents,finance,procurement,equipment,hr,contracts,qhse,legal}', 1),
 ('SHARED-FIN',   'GROUP', 'GROUP', 'Comptabilité et finances',        'shared_service', 0, '{finance,crm,contracts}', 2),
 ('SHARED-HR',    'GROUP', 'GROUP', 'Ressources humaines',             'shared_service', 0, '{hr}', 3),
 ('SHARED-LEGAL', 'GROUP', 'GROUP', 'Juridique',                       'shared_service', 0, '{contracts,legal}', 4),
 ('SHARED-IT',    'GROUP', 'GROUP', 'Informatique et cybersécurité',   'shared_service', 0, '{}', 5),
 ('SHARED-AI',    'GROUP', 'GROUP', 'ilk.medater AI',                  'shared_service', 0, '{}', 6),

 -- eurl medater (R+1)
 ('CONST',        'GROUP', 'CONST', 'eurl medater — entreprise de construction', 'subsidiary', 1, '{}', 10),
 ('CONST-DIR',    'CONST', 'CONST', 'Direction de l''entreprise',     'direction',  1, '{crm,projects,sites,studies,documents,finance,procurement,equipment,hr,contracts,qhse}', 11),
 ('CONST-TECH',   'CONST', 'CONST', 'Direction technique',             'department', 1, '{projects,studies,sites,documents}', 12),
 ('CONST-SITE',   'CONST', 'CONST', 'Direction des chantiers',         'department', 1, '{projects,sites,qhse,equipment,documents}', 13),
 ('CONST-PROC',   'CONST', 'CONST', 'Achats et logistique',            'department', 1, '{procurement,crm,equipment}', 14),
 ('CONST-EST',    'CONST', 'CONST', 'Études de prix et appels d’offres', 'department', 1, '{contracts,projects,crm,documents}', 15),
 ('CONST-QHSE',   'CONST', 'CONST', 'Qualité et HSE',                  'department', 1, '{qhse,sites}', 16),
 ('CONST-FIN',    'CONST', 'CONST', 'Finances et contrats',            'department', 1, '{finance,contracts,crm}', 17),
 ('CONST-HR',     'CONST', 'CONST', 'Ressources humaines (filiale)',   'service',    1, '{hr}', 18),
 ('CONST-PARC',   'CONST', 'CONST', 'Parc matériel et maintenance',    'service',    1, '{equipment}', 19),
 ('CONST-DOC',    'CONST', 'CONST', 'Documentation',                   'service',    1, '{documents}', 20),
 ('CONST-LEGAL',  'CONST', 'CONST', 'Juridique des marchés, réclamations et contentieux', 'service', 1, '{contracts,legal}', 21),

 -- cabinet ILK (R+2)
 ('ARCH',         'GROUP', 'ARCH', 'cabinet ILK — architecture et ingénierie', 'subsidiary', 2, '{}', 30),
 ('ARCH-DIR',     'ARCH',  'ARCH', 'Direction du cabinet',             'direction',  2, '{crm,projects,studies,documents,finance,hr,contracts,legal}', 31),
 ('ARCH-ARC',     'ARCH',  'ARCH', 'Pôle Architecture',                'department', 2, '{projects,studies,documents}', 32),
 ('ARCH-GC',      'ARCH',  'ARCH', 'Pôle Génie civil',                 'department', 2, '{projects,studies,documents}', 33),
 ('ARCH-LEGAL',   'ARCH',  'ARCH', 'Pôle Juridique',                   'department', 2, '{contracts,legal,documents}', 34),
 ('ARCH-MEP',     'ARCH',  'ARCH', 'Pôle MEP',                         'department', 2, '{projects,studies,documents}', 35),
 ('ARCH-MEP-COORD','ARCH-MEP','ARCH','Coordination MEP',               'coordination', 2, '{projects,studies,documents}', 36),
 ('ARCH-MEP-CFO', 'ARCH-MEP','ARCH','MEP 01 — Courant fort (CFO)',     'specialty',  2, '{projects,studies,documents}', 37),
 ('ARCH-MEP-CFA', 'ARCH-MEP','ARCH','MEP 02 — Courants faibles (CFA)', 'specialty',  2, '{projects,studies,documents}', 38),
 ('ARCH-MEP-FIRE','ARCH-MEP','ARCH','MEP 03 — Détection et extinction incendie', 'specialty', 2, '{projects,studies,documents}', 39),
 ('ARCH-MEP-PLUMB','ARCH-MEP','ARCH','MEP 04 — Plomberie hydraulique',  'specialty',  2, '{projects,studies,documents}', 40),
 ('ARCH-MEP-HVAC','ARCH-MEP','ARCH','MEP 05 — Climatisation HVAC',     'specialty',  2, '{projects,studies,documents}', 41),
 ('ARCH-MEP-AIR', 'ARCH-MEP','ARCH','MEP 06 — Aéraulique',             'specialty',  2, '{projects,studies,documents}', 42);
