CREATE OR REPLACE VIEW public.sexcoin_live_chain AS 
 SELECT b.block_id,
    cc.block_height,
    bb.block_ntime,
    bb.block_chain_work,
    bb.block_nbits
   FROM chain_candidate cc
     LEFT JOIN block b ON b.block_id = cc.block_id
     LEFT JOIN block bb ON b.block_id = bb.block_id
  WHERE cc.chain_id = 1::numeric AND cc.in_longest = 1::numeric;

ALTER TABLE public.sexcoin_live_chain
  OWNER TO coiner;
  
CREATE TABLE public.richlist
(
  address character varying NOT NULL,
  balance numeric,
  CONSTRAINT richlist_pk PRIMARY KEY (address)
)
WITH (
  OIDS=FALSE
);
ALTER TABLE public.richlist
  OWNER TO coiner;

--INSERT INTO configvar(configvar_name, configvar_value) VALUES('richlist_date','Saturday, June 02, 2018 03:38');
UPDATE configvar SET configvar_value = 'Saturday, June 02, 2018 03:38' WHERE configvar_name = 'richlist_date'; 
