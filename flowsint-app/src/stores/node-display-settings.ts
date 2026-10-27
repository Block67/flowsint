import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type * as LucideIcons from 'lucide-react'

export type ItemType =
  | 'domain'
  | 'email'
  | 'ip'
  | 'phone'
  | 'username'
  | 'organization'
  | 'individual'
  | 'socialaccount'
  | 'cryptowallet'
  | 'cryptowallettransaction'
  | 'cryptonft'
  | 'transaction'
  | 'mobilemoneyaccount'
  | 'merchant'
  | 'website'
  | 'phrase'
  | 'breach'
  | 'credential'
  | 'device'
  | 'document'
  | 'file'
  | 'location'
  | 'affiliation'
  | 'alias'
  | 'bankaccount'
  | 'creditcard'
  | 'leak'
  | 'message'
  | 'reputationscore'
  | 'riskprofile'
  | 'custom'

export const ITEM_TYPES: ItemType[] = [
  'domain',
  'email',
  'ip',
  'phone',
  'username',
  'organization',
  'individual',
  'socialaccount',
  'cryptowallet',
  'cryptowallettransaction',
  'cryptonft',
  'transaction',
  'mobilemoneyaccount',
  'merchant',
  'website',
  'phrase',
  'breach',
  'credential',
  'device',
  'document',
  'file',
  'location',
  'affiliation',
  'alias',
  'bankaccount',
  'creditcard',
  'leak',
  'message',
  'reputationscore',
  'riskprofile',
  'custom'
]

// Icon mapping for each item type (Lucide icons)
export const TYPE_TO_ICON: Record<string, keyof typeof LucideIcons> = {
  domain: 'Globe',
  email: 'Mail',
  ip: 'Network',
  phone: 'Phone',
  username: 'UserPlus',
  organization: 'Building2',
  individual: 'User',
  socialaccount: 'Share2',
  cryptowallet: 'Wallet',
  cryptowallettransaction: 'ArrowRightLeft',
  cryptonft: 'Image',
  transaction: 'ArrowRightLeft',
  mobilemoneyaccount: 'Smartphone',
  merchant: 'Store',
  website: 'Globe',
  phrase: 'Quote',
  breach: 'ShieldAlert',
  credential: 'Key',
  device: 'Smartphone',
  document: 'FileText',
  file: 'File',
  location: 'MapPin',
  affiliation: 'Link2',
  alias: 'UserCog',
  bankaccount: 'Landmark',
  creditcard: 'CreditCard',
  leak: 'Droplet',
  message: 'MessageSquare',
  reputationscore: 'Star',
  riskprofile: 'AlertTriangle',
  default: 'FileQuestion',
  custom: 'Cog'
}

const DEFAULT_COLORS: Record<ItemType, string> = {
  domain: '#66A892', // vert sauge
  email: '#8E7CC3', // violet pastel
  ip: '#5AA1C8', // orange chaud
  phone: '#4CB5AE', // teal doux
  username: '#8B83C1', // pervenche
  organization: '#BCA18A', // taupe clair
  individual: '#4C8EDA', // bleu moyen
  socialaccount: '#A76DAA', // mauve
  cryptowallet: '#D4B030', // or clair
  cryptowallettransaction: '#BFA750', // or chaud
  cryptonft: '#A5BF50', // vert lime doux
  transaction: '#BFA750', // or chaud
  mobilemoneyaccount: '#E3A857', // orange sable
  merchant: '#BCA18A', // taupe clair
  website: '#D279A6', // rose pastel
  phrase: '#BFA77A', // beige chaud
  breach: '#CC7A7A', // rose chaud
  credential: '#D4B030', // doré doux
  device: '#E3A857', // orange sable
  document: '#8F9CA3', // gris bleuté
  file: '#8F9CA3', // gris bleuté
  location: '#E57373', // rouge rosé
  affiliation: '#66A892', // vert sauge
  alias: '#A36FA3', // violet
  bankaccount: '#D4B030', // or clair
  creditcard: '#285E8E', // bleu profond
  leak: '#7C9CBF', // bleu acier
  message: '#897FC9', // violet lavande
  reputationscore: '#6FA8DC', // bleu clair
  riskprofile: '#D97474', // rouge doux
  custom: '#9B6F9B'
}

const hslToHex = (h: number, s: number, l: number): string => {
  const s1 = s / 100
  const l1 = l / 100
  const c = (1 - Math.abs(2 * l1 - 1)) * s1
  const hh = h / 60
  const x = c * (1 - Math.abs((hh % 2) - 1))
  let r1 = 0,
    g1 = 0,
    b1 = 0
  if (hh >= 0 && hh < 1) {
    r1 = c
    g1 = x
    b1 = 0
  } else if (hh >= 1 && hh < 2) {
    r1 = x
    g1 = c
    b1 = 0
  } else if (hh >= 2 && hh < 3) {
    r1 = 0
    g1 = c
    b1 = x
  } else if (hh >= 3 && hh < 4) {
    r1 = 0
    g1 = x
    b1 = c
  } else if (hh >= 4 && hh < 5) {
    r1 = x
    g1 = 0
    b1 = c
  } else {
    r1 = c
    g1 = 0
    b1 = x
  }
  const m = l1 - c / 2
  const r = Math.round((r1 + m) * 255)
  const g = Math.round((g1 + m) * 255)
  const b = Math.round((b1 + m) * 255)
  const toHex = (v: number) => v.toString(16).padStart(2, '0')
  return `#${toHex(r)}${toHex(g)}${toHex(b)}`
}

const randomizeColors = (colors: Record<ItemType, string>): Record<ItemType, string> => {
  const next: Record<ItemType, string> = { ...colors }
  ITEM_TYPES.forEach((t) => {
    // Simple, slightly vibrant but not neon
    const h = Math.floor(Math.random() * 360)
    const s = Math.floor(45 + Math.random() * 15) // 45% - 60%
    const l = Math.floor(65 + Math.random() * 10) // 65% - 75%
    next[t] = hslToHex(h, s, l)
  })
  return next
}

interface NodesDisplaySettingsState {
  colors: Record<ItemType, string>
  customIcons: Record<string, keyof typeof LucideIcons>
  setColor: (itemType: ItemType, color: string) => void
  setIcon: (itemType: string, iconName: keyof typeof LucideIcons) => void
  resetSettings: () => void
  randomizeColors: () => void
  resetAll: () => void
  getIcon: (itemType: ItemType) => keyof typeof LucideIcons
}

export const useNodesDisplaySettings = create<NodesDisplaySettingsState>()(
  persist(
    (set, get) => ({
      colors: { ...DEFAULT_COLORS },
      customIcons: { ...TYPE_TO_ICON },
      setColor: (itemType, color) =>
        set((state) => ({
          colors: {
            ...state.colors,
            [itemType]: color
          }
        })),
      setIcon: (itemType, iconName) =>
        set((state) => ({
          customIcons: {
            ...state.customIcons,
            [itemType]: iconName
          }
        })),
      resetSettings: () => set({ colors: { ...DEFAULT_COLORS }, customIcons: TYPE_TO_ICON }),
      randomizeColors: () => set({ colors: randomizeColors(get().colors) }),
      resetAll: () =>
        set({
          colors: { ...DEFAULT_COLORS },
          customIcons: {}
        }),
      getIcon: (itemType) => {
        const customIcon = get().customIcons[itemType]
        if (customIcon) return customIcon
        return TYPE_TO_ICON[itemType] || TYPE_TO_ICON.default
      }
    }),
    {
      name: 'nodes-display-settings'
    }
  )
)
