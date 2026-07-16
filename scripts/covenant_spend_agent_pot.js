#!/usr/bin/env node
/**
 * Spend from a covenant-bound pot UTXO on testnet-10 (#1074 WASM).
 *
 * Usage: node covenant_spend_agent_pot.js '<json>'
 * Payload:
 *   key_path, wasm_dir, network?, compute_budget?, fee_sompi?,
 *   amount_sompi, destination, covenant_id? (optional filter),
 *   max_tx_sompi?, allowed_destinations?[]  (client-side checks; also enforced in Python)
 *
 * Continues covenant binding on change output when change remains.
 * Prints one JSON line. Never prints private keys.
 */
'use strict';

const fs = require('fs');
const path = require('path');

function emit(obj) {
  console.log(JSON.stringify(obj, (_, v) => (typeof v === 'bigint' ? v.toString() : v)));
}
function fail(err, extra = {}) {
  emit({ ok: false, error: String(err && err.message ? err.message : err), ...extra });
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
      fail('WebSocket unavailable');
    }
  }

  let kaspa;
  try {
    kaspa = require(wasmDir);
  } catch (e) {
    fail('require wasm: ' + e, { step: 'require' });
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
  if (!/^[0-9a-fA-F]{64}$/.test(keyHex)) fail('key must be 64 hex chars');

  const fee = BigInt(cfg.fee_sompi || 500_000);
  const budget = Number(cfg.compute_budget || 10);
  const networkId = cfg.network || 'testnet-10';
  const amount = BigInt(cfg.amount_sompi || 0);
  const destination = (cfg.destination || '').trim();
  const filterCov = (cfg.covenant_id || '').trim();
  const maxTx = BigInt(cfg.max_tx_sompi || 0);
  const dests = cfg.allowed_destinations || [];

  if (amount <= 0n) fail('amount_sompi must be positive', { step: 'amounts' });
  if (!destination) fail('destination required', { step: 'amounts' });
  if (maxTx > 0n && amount > maxTx) {
    fail('amount exceeds max_tx_sompi', { step: 'policy', amount: amount.toString(), max_tx: maxTx.toString() });
  }
  // dest allowlist optional in JS if provided
  if (dests.length > 0 && !dests.includes(destination)) {
    // allow owner return if destination matches key address (checked after derive)
  }

  const priv = new PrivateKey(keyHex);
  let address;
  try {
    address = priv.toKeypair().toAddress(networkId);
  } catch (_) {
    address = priv.toKeypair().toAddress('testnet');
  }
  const addressStr = address.toString();

  if (dests.length > 0 && !dests.includes(destination) && destination !== addressStr) {
    fail('destination not on allowlist', { step: 'policy', destination });
  }

  const rpc = new RpcClient({ resolver: new Resolver(), networkId });
  await rpc.connect();

  let utxosResp;
  try {
    utxosResp = await rpc.getUtxosByAddresses({ addresses: [addressStr] });
  } catch (_) {
    utxosResp = await rpc.getUtxosByAddresses([addressStr]);
  }
  const entries = utxosResp.entries || [];

  // Prefer largest UTXO; optionally match covenant_id when visible
  let best = null;
  let bestAmt = -1n;
  for (const e of entries) {
    const amt = BigInt(e.amount);
    if (filterCov) {
      let cid = '';
      try {
        const c = e.covenantId;
        cid = c && c.toString ? c.toString() : String(c || '');
      } catch (_) {
        cid = '';
      }
      // RPC often omits covenantId — if filter set and we can't see it, still allow largest
      if (cid && cid.length >= 16 && cid !== filterCov) continue;
    }
    if (amt > bestAmt) {
      best = e;
      bestAmt = amt;
    }
  }
  if (!best) {
    await rpc.disconnect();
    fail('no UTXO to spend', { address: addressStr, step: 'select_utxo' });
  }
  if (bestAmt < amount + fee) {
    await rpc.disconnect();
    fail('UTXO too small for amount+fee', {
      utxo: bestAmt.toString(),
      need: (amount + fee).toString(),
      step: 'amounts',
    });
  }

  const change = bestAmt - amount - fee;
  const MIN = 10_000_000n; // avoid dust storage mass
  let outs;
  if (change === 0n) {
    outs = [{ address: destination, amount }];
  } else if (change < MIN) {
    // fold dust change into payment if dest is self; else reject
    if (destination === addressStr) {
      outs = [{ address: destination, amount: bestAmt - fee }];
    } else {
      await rpc.disconnect();
      fail('change would be dust; send larger amount or spend-to-self', {
        change: change.toString(),
        step: 'amounts',
      });
    }
  } else {
    outs = [
      { address: destination, amount },
      { address: addressStr, amount: change },
    ];
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
    await rpc.disconnect();
    fail(e, { step: 'create_transaction' });
  }

  // Continue covenant on change (index 1) if present; payment is unbound (or rebind pot)
  // Lab style for transition: re-bind same id on the continuing pot output.
  // When payment goes external, change keeps covenant lineage.
  let covenantIdStr = filterCov || null;
  try {
    if (tx.outputs.length >= 2) {
      const op = tx.inputs[0].previousOutpoint;
      // Use existing filter id if provided; else compute new from change as auth out index 1? 
      // For continuation, authorizing_input 0, same id as spent covenant.
      if (filterCov && filterCov.length === 64) {
        // reconstruct Hash via covenantId on a dummy is hard; set binding from recompute
        // Recompute genesis-style id is WRONG for transition. For transition, reuse spent id.
        // WASM: new CovenantBinding(0, Hash) — try Hash from string if available
        let idObj = null;
        if (kaspa.Hash && kaspa.Hash.fromHex) {
          idObj = kaspa.Hash.fromHex(filterCov);
        } else if (kaspa.Hash) {
          try {
            idObj = new kaspa.Hash(filterCov);
          } catch (_) {
            idObj = null;
          }
        }
        if (idObj) {
          tx.outputs[1].covenant = new CovenantBinding(0, idObj);
          covenantIdStr = filterCov;
        }
      }
    }
    for (const inp of tx.inputs) {
      if (inp.computeBudget == null) inp.computeBudget = budget;
    }
  } catch (e) {
    await rpc.disconnect();
    fail(e, { step: 'covenant_bind' });
  }

  let signed;
  try {
    signed = signTransaction(tx, [priv], false);
  } catch (e) {
    await rpc.disconnect();
    fail(e, { step: 'sign' });
  }

  let submitRes;
  try {
    submitRes = await rpc.submitTransaction({ transaction: signed });
  } catch (e1) {
    try {
      submitRes = await rpc.submitTransaction(signed);
    } catch (e2) {
      await rpc.disconnect();
      fail(e2, { step: 'submit', first: String(e1 && e1.message ? e1.message : e1) });
    }
  }
  await rpc.disconnect().catch(() => {});

  const networkTxid =
    (submitRes && (submitRes.transactionId || submitRes.transaction_id)) ||
    (typeof signed.id === 'string' ? signed.id : String(signed.id));

  emit({
    ok: true,
    network: networkId,
    address: addressStr,
    destination,
    amount_sompi: amount.toString(),
    change_sompi: change > 0n ? change.toString() : '0',
    fee_sompi: fee.toString(),
    compute_budget: budget,
    covenant_id: covenantIdStr,
    txid: networkTxid,
    tooling: 'wasm-pr1074-spend',
    enforcement: 'soft_policy_precheck_plus_broadcast',
    on_chain_hard_cap: false,
  });
}

main().catch((e) => fail(e, { step: 'main' }));
