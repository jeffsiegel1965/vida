#!/usr/bin/env node
/**
 * Fund a covenant-bound agent pot on testnet-10 (#1074 WASM).
 * Usage: node covenant_fund_agent_pot.js '<json>'
 * Prints one JSON line. Never prints private keys.
 */
'use strict';

const fs = require('fs');
const path = require('path');

function emit(obj) {
  console.log(JSON.stringify(obj, (_, v) => (typeof v === 'bigint' ? v.toString() : v)));
}

function fail(err, extra = {}) {
  const msg = err && err.message ? err.message : String(err);
  emit({ ok: false, error: msg, ...extra });
  process.exit(1);
}

async function main() {
  const raw = process.argv[2];
  if (!raw) fail('missing json payload');
  let cfg;
  try {
    cfg = JSON.parse(raw);
  } catch (e) {
    fail('invalid json: ' + e);
  }

  const wasmDir = path.resolve(cfg.wasm_dir || process.env.VIDA_KASPA_WASM || '');
  if (!wasmDir) fail('wasm_dir required');

  if (typeof globalThis.WebSocket === 'undefined') {
    try {
      globalThis.WebSocket = require('websocket').w3cwebsocket;
    } catch (_) {
      fail('WebSocket unavailable (need Node 22+ or websocket package)');
    }
  }

  let kaspa;
  try {
    kaspa = require(wasmDir);
  } catch (e) {
    fail('require wasm failed: ' + e, { wasmDir, step: 'require' });
  }

  const {
    PrivateKey,
    RpcClient,
    Resolver,
    createTransaction,
    signTransaction,
    ComputeCommit,
    CovenantBinding,
    covenantId,
  } = kaspa;

  const keyPath = cfg.key_path || '/tmp/kascov-lab-key.hex';
  let keyHex;
  try {
    keyHex = fs.readFileSync(keyPath, 'utf8').trim();
  } catch (e) {
    fail('read key: ' + e, { step: 'read_key' });
  }
  if (!/^[0-9a-fA-F]{64}$/.test(keyHex)) fail('key must be 64 hex chars', { step: 'key_format' });

  const fee = BigInt(cfg.fee_sompi || 500_000);
  const budget = Number(cfg.compute_budget || 10);
  const networkId = cfg.network || 'testnet-10';
  const singleOutput = cfg.single_output !== false;
  const maxTx = BigInt(cfg.max_tx_sompi || 0);
  const dests = cfg.allowed_destinations || [];
  const policyHash = cfg.policy_hash || null;

  let priv;
  try {
    priv = new PrivateKey(keyHex);
  } catch (e) {
    fail(e, { step: 'private_key' });
  }

  let address;
  try {
    address = priv.toKeypair().toAddress(networkId);
  } catch (_) {
    address = priv.toKeypair().toAddress('testnet');
  }
  const addressStr = address.toString();

  const rpc = new RpcClient({ resolver: new Resolver(), networkId });
  try {
    await rpc.connect();
  } catch (e) {
    fail(e, { step: 'connect' });
  }

  let utxosResp;
  try {
    utxosResp = await rpc.getUtxosByAddresses({ addresses: [addressStr] });
  } catch (e) {
    try {
      utxosResp = await rpc.getUtxosByAddresses([addressStr]);
    } catch (e2) {
      await rpc.disconnect().catch(() => {});
      fail(e2, { step: 'get_utxos', first: String(e) });
    }
  }
  const entries = utxosResp.entries || [];

  let best = null;
  let bestAmt = -1n;
  for (const e of entries) {
    const amount = BigInt(e.amount);
    // only skip if covenant id is a non-empty string/hash
    const cid = e.covenantId;
    if (cid !== undefined && cid !== null && String(cid) !== '' && String(cid) !== 'undefined') {
      // still allow if wasm returns empty object — only skip real ids
      try {
        const s = cid.toString ? cid.toString() : String(cid);
        if (s && s.length >= 16 && s !== '[object Object]') continue;
      } catch (_) {
        /* keep */
      }
    }
    if (amount > bestAmt) {
      best = e;
      bestAmt = amount;
    }
  }
  if (!best) {
    await rpc.disconnect().catch(() => {});
    fail('no plain funding UTXO', { address: addressStr, step: 'select_utxo' });
  }
  if (bestAmt <= fee + 1_000_000n) {
    await rpc.disconnect().catch(() => {});
    fail('funding UTXO too small', { amount: bestAmt.toString(), step: 'select_utxo' });
  }

  let outs;
  let potSompi;
  if (singleOutput || !cfg.pot_sompi) {
    potSompi = bestAmt - fee;
    outs = [{ address: addressStr, amount: potSompi }];
  } else {
    potSompi = BigInt(cfg.pot_sompi);
    const change = bestAmt - potSompi - fee;
    const MIN = 10_000_000n;
    if (potSompi < MIN || change < MIN) {
      await rpc.disconnect().catch(() => {});
      fail('pot/change dust risk; use single_output or larger amounts', {
        pot: potSompi.toString(),
        change: change.toString(),
        step: 'amounts',
      });
    }
    outs = [
      { address: addressStr, amount: potSompi },
      { address: addressStr, amount: change },
    ];
  }

  if (maxTx > 0n && maxTx > potSompi) {
    await rpc.disconnect().catch(() => {});
    fail('max_tx_sompi cannot exceed pot_sompi', {
      max_tx_sompi: maxTx.toString(),
      pot_sompi: potSompi.toString(),
      step: 'amounts',
    });
  }

  let tx;
  try {
    tx = createTransaction(
      [best],
      outs,
      0n,
      undefined,
      ComputeCommit.fromComputeBudget(budget),
      1
    );
  } catch (e) {
    await rpc.disconnect().catch(() => {});
    fail(e, { step: 'create_transaction' });
  }

  let covenantIdStr;
  try {
    const op = tx.inputs[0].previousOutpoint;
    const out0 = tx.outputs[0];
    const id = covenantId(
      { transactionId: String(op.transactionId), index: Number(op.index) },
      [{ index: 0, output: out0 }]
    );
    covenantIdStr = id.toString();
    out0.covenant = new CovenantBinding(0, id);
    for (const inp of tx.inputs) {
      if (inp.computeBudget == null) inp.computeBudget = budget;
    }
  } catch (e) {
    await rpc.disconnect().catch(() => {});
    fail(e, { step: 'covenant_bind' });
  }

  let signed;
  try {
    signed = signTransaction(tx, [priv], false);
  } catch (e) {
    await rpc.disconnect().catch(() => {});
    fail(e, { step: 'sign' });
  }

  let submitRes;
  try {
    submitRes = await rpc.submitTransaction({ transaction: signed });
  } catch (e1) {
    try {
      submitRes = await rpc.submitTransaction(signed);
    } catch (e2) {
      await rpc.disconnect().catch(() => {});
      fail(e2, { step: 'submit', first: String(e1 && e1.message ? e1.message : e1) });
    }
  }
  try {
    await rpc.disconnect();
  } catch (_) {
    /* ignore */
  }

  const networkTxid =
    (submitRes && (submitRes.transactionId || submitRes.transaction_id)) ||
    (typeof signed.id === 'string' ? signed.id : String(signed.id));

  emit({
    ok: true,
    network: networkId,
    address: addressStr,
    funding_amount_sompi: bestAmt.toString(),
    pot_sompi: potSompi.toString(),
    fee_sompi: fee.toString(),
    compute_budget: budget,
    covenant_id: covenantIdStr,
    txid: networkTxid,
    hard_rules_attached: {
      max_tx_sompi: maxTx.toString(),
      allowed_destinations: dests,
      policy_hash: policyHash,
      on_chain_max_tx: false,
      on_chain_dest: false,
      note: 'policy recorded off-chain; pot UTXO is covenant-bound lineage',
    },
    tooling: 'wasm-pr1074',
  });
}

main().catch((e) => fail(e, { step: 'main' }));
