#!/usr/bin/env python3
"""Live testnet-10 integration test. Verifies the full pipeline works using async directly."""

import asyncio, sys, os, json
sys.path.insert(0, os.path.expanduser("~/.hermes/projects/vida-release"))
os.environ["VIDA_LIVE_TEST"] = "1"

async def test_live():
    results = []
    def check(name, condition, detail=""):
        status = "✅" if condition else "❌"
        results.append({"name": name, "ok": condition})
        print(f"  {status} {name}" + (f" — {detail}" if detail else ""))
    
    print("=== LIVE TESTNET-10 INTEGRATION TEST ===\n")
    
    from vida.plugins.covenant.kaspa_rpc import _get_client, _disconnect, _network_id
    from kaspa import PrivateKey, NetworkType, Address, PaymentOutput, create_transaction, sign_transaction, sompi_to_kaspa, CovenantBinding
    import hashlib
    
    # 1. Connect
    print("1. Network")
    client = await _get_client()
    # Reconnect with testnet-10
    client.set_network_id("testnet-10")
    info = await client.get_block_dag_info()
    daa = info.get("virtualDaaScore", "?")
    check("Connected to testnet-10", True, f"DAA {daa}")
    
    # 2. Key
    key_hex = open("/tmp/vida-covenant-key.hex").read().strip()
    priv = PrivateKey(key_hex)
    addr = str(priv.to_address(NetworkType.Testnet))
    print(f"\n2. Deployer: {addr}")
    
    bal = await client.get_balances_by_addresses(request={"addresses": [addr]})
    entries = bal.get("entries", [])
    balance_sompi = entries[0].get("balance", 0) if entries else 0
    balance_kas = sompi_to_kaspa(balance_sompi)
    check("Balance > 0", balance_sompi > 0, f"{balance_kas} KAS")
    
    # 3. Get UTXOs
    print(f"\n3. UTXOs")
    utxos = await client.get_utxos_by_addresses(request={"addresses": [addr]})
    utxo_entries = utxos.get("entries", [])
    check("UTXOs available", len(utxo_entries) > 0, f"{len(utxo_entries)} UTXOs")
    
    if not utxo_entries:
        print("No UTXOs, cannot test transaction building")
        return False
    
    utxo = utxo_entries[0]
    utxo_entry = utxo.get("utxoEntry", utxo) if isinstance(utxo, dict) else utxo
    amt = int(utxo_entry.get("amount", 0)) if isinstance(utxo_entry, dict) else 0
    print(f"   Largest UTXO: {sompi_to_kaspa(amt)} KAS")
    
    # 4. Build a minimal transaction
    print(f"\n4. Build transaction")
    try:
        send_amt = min(amt - 100_000, 100_000_000)  # 1 KAS or less
        fee = 10_000
        change = amt - send_amt - fee
        
        out1 = PaymentOutput(addr, send_amt)
        out2 = PaymentOutput(addr, change)
        
        tx = create_transaction(
            utxo_entry_source=[utxo],
            outputs=[out1, out2],
            priority_fee=fee,
            sig_op_count=1,
        )
        check("Transaction built", True, f"mass={tx.mass}, id={tx.id[:16]}")
        
        # 5. Sign
        signed = sign_transaction(tx, [priv], True)
        check("Transaction signed", True)
        
        # 6. Submit via SDK with correct format
        print(f"\n5. Submit via SDK")
        tx_dict = signed.to_dict()
        try:
            result = await client.submit_transaction(request={
                "transaction": tx_dict,
                "allowOrphan": False,
            })
            txid = result.get("txid", "") if isinstance(result, dict) else str(result)
            if txid:
                check("SDK submit succeeded", True, f"txid {txid[:16]}...")
                print(f"   Explorer: https://tn10.kaspa.org/explorer/transactions/{txid}")
            else:
                check("SDK submit returned unexpected", False, str(result)[:80])
        except (TypeError, RuntimeError, KeyError) as e:
            check("SDK submit", False, f"failed: {e}")
            
            # 7. Fall back to REST API
            print(f"\n6. Fall back to REST API")
            try:
                import requests
                class SafeEncoder(json.JSONEncoder):
                    def default(self, o):
                        return str(o)
                
                # Convert SDK format to REST API format
                # SDK: value → REST: amount
                # SDK: outputs[].scriptPublicKey.script → REST: outputs[].scriptPublicKey.scriptPublicKey
                rest_inputs = []
                for inp in tx_dict.get("inputs", []):
                    po = inp.get("previousOutpoint", {})
                    rest_inputs.append({
                        "previousOutpoint": {
                            "transactionId": po.get("transactionId", ""),
                            "index": po.get("index", 0),
                        },
                        "signatureScript": inp.get("signatureScript", ""),
                        "sequence": inp.get("sequence", 0),
                        "sigOpCount": inp.get("sigOpCount", inp.get("sigOpCount", 1)),
                    })
                
                rest_outputs = []
                for o in tx_dict.get("outputs", []):
                    spk = o.get("scriptPublicKey", {})
                    rest_outputs.append({
                        "amount": o.get("value", o.get("amount", 0)),
                        "scriptPublicKey": {
                            "version": spk.get("version", 0),
                            "scriptPublicKey": spk.get("script", ""),
                        },
                    })
                
                rest_dict = {
                    "version": tx_dict.get("version", 0),
                    "inputs": rest_inputs,
                    "outputs": rest_outputs,
                    "lockTime": tx_dict.get("lockTime", 0),
                    "subnetworkId": tx_dict.get("subnetworkId", "0000000000000000000000000000000000000000"),
                    "gas": tx_dict.get("gas", 0),
                    "payload": tx_dict.get("payload", ""),
                    "mass": tx_dict.get("mass", 0),
                }
                
                safe_dict = json.loads(json.dumps(rest_dict, cls=SafeEncoder))
                resp = requests.post(
                    "https://api-tn10.kaspa.org/transactions",
                    json={"transaction": safe_dict, "allowOrphan": False},
                    timeout=15,
                )
                if resp.ok:
                    result = resp.json()
                    txid = result.get("txid", "")
                    check("REST API submit succeeded", bool(txid), f"txid: {txid[:16] if txid else '?'}...")
                    if txid:
                        explorer_url = f"https://tn10.kaspa.org/explorer/transactions/{txid}"
                        print(f"   Explorer: {explorer_url}")
                        # Save to results file
                        with open("/tmp/vida_live_test_result.json", "w") as f:
                            json.dump({"txid": txid, "explorer": explorer_url, "source": "rest_api"}, f)
                else:
                    check("REST API submit", False, f"HTTP {resp.status_code}: {resp.text[:150]}")
            except Exception as e:
                check("REST API submit", False, f"error: {e}")
    
    except Exception as e:
        check("Transaction build/sign", False, f"error: {e}")
    
    # 8. Disconnect
    await _disconnect()
    
    # Summary
    print(f"\n{'='*50}")
    passed = sum(1 for r in results if r["ok"])
    failed = sum(1 for r in results if not r["ok"])
    print(f"RESULTS: {passed}/{len(results)} passed")
    if failed:
        for r in results:
            if not r["ok"]:
                print(f"  ❌ {r['name']}")
    print(f"{'='*50}")
    return failed == 0

if __name__ == "__main__":
    success = asyncio.run(test_live())
    sys.exit(0 if success else 1)