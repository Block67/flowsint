// 005_transaction_indexes.cypher
// Indexes for transaction analysis: account node types and TRANSACTION edges.
// All statements are idempotent (IF NOT EXISTS)

CREATE INDEX idx_sketch_id_mobilemoneyaccount IF NOT EXISTS FOR (n:mobilemoneyaccount) ON (n.sketch_id);
CREATE INDEX idx_sketch_id_merchant IF NOT EXISTS FOR (n:merchant) ON (n.sketch_id);
CREATE INDEX idx_nodeLabel_mobilemoneyaccount IF NOT EXISTS FOR (n:mobilemoneyaccount) ON (n.nodeLabel);
CREATE INDEX idx_nodeLabel_merchant IF NOT EXISTS FOR (n:merchant) ON (n.nodeLabel);
CREATE INDEX idx_nodeLabel_bankaccount IF NOT EXISTS FOR (n:bankaccount) ON (n.nodeLabel);
CREATE INDEX idx_nodeLabel_creditcard IF NOT EXISTS FOR (n:creditcard) ON (n.nodeLabel);

// TRANSACTION relationships are merged on (sketch_id, edge_key) and filtered
// by time window and amount in flow analysis.
CREATE INDEX idx_transaction_edge_key IF NOT EXISTS FOR ()-[r:TRANSACTION]-() ON (r.sketch_id, r.edge_key);
CREATE INDEX idx_transaction_timestamp IF NOT EXISTS FOR ()-[r:TRANSACTION]-() ON (r.timestamp_epoch);
CREATE INDEX idx_transaction_amount IF NOT EXISTS FOR ()-[r:TRANSACTION]-() ON (r.amount);
