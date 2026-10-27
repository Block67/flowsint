import { memo } from 'react'
import { HelpCircle } from 'lucide-react'
import { Dialog, DialogContent, DialogTrigger } from '../ui/dialog'
import { Button } from '../ui/button'

const InfoDialog = () => {
  return (
    <>
      <Dialog>
        <DialogTrigger asChild>
          <div>
            <Button variant="ghost" size="sm" className="h-6 gap-1 text-xs">
              <HelpCircle className="h-3 w-3 opacity-60" />
            </Button>
          </div>
        </DialogTrigger>
        <DialogContent className="sm:max-w-2xl">
          <div className="p-2">
            <div className="p-2 text-sm space-y-4 overflow-y-auto max-h-[80vh]">
              <h2 className="text-base font-semibold flex items-center gap-2">About Flowtrace</h2>
              <p>
                <strong>Flowtrace</strong> is a <strong>transaction analysis platform</strong> for
                following money across{' '}
                <strong>bank accounts, mobile money and crypto wallets</strong>. Every account is a
                node and every transaction is an edge, so flows of funds can be read directly on the
                graph.
              </p>

              <h3 className="font-semibold">What Flowtrace Does</h3>
              <ul className="list-disc list-inside space-y-1">
                <li>
                  <strong>Imports statements</strong> from CSV or Excel files (bank, mobile money,
                  card) with automatic column mapping.
                </li>
                <li>
                  <strong>Pulls on-chain transfers</strong> for Ethereum and EVM chains, ERC-20 and
                  TRC-20 tokens, and Bitcoin, and checks addresses against the{' '}
                  <strong>OFAC sanctions lists</strong>.
                </li>
                <li>
                  <strong>Detects suspicious patterns</strong>: fan-in, fan-out, pass-through (money
                  mule) accounts, structuring below a threshold and circular flows.
                </li>
                <li>
                  <strong>Traces funds</strong> upstream or downstream from any account, and
                  summarizes what each account received, sent and kept.
                </li>
              </ul>

              <h3 className="font-semibold">Use Cases</h3>
              <ul className="list-disc list-inside space-y-1">
                <li>
                  Fraud and <strong>scam investigations</strong>: where did the victim&apos;s money
                  go?
                </li>
                <li>
                  <strong>AML reviews</strong> of mule networks and layering
                </li>
                <li>
                  Crypto <strong>wallet tracing</strong> and sanctions exposure
                </li>
              </ul>

              <p className="text-xs text-muted-foreground">
                Flowtrace is based on{' '}
                <a
                  href="https://github.com/reconurge/flowsint"
                  target="_blank"
                  rel="noreferrer"
                  className="underline"
                >
                  Flowsint
                </a>
                , licensed under Apache 2.0.
              </p>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </>
  )
}

export default memo(InfoDialog)
