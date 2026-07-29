# Component API

## Button

```ts
interface ButtonProps
  extends Omit<React.ButtonHTMLAttributes<HTMLButtonElement>, 'color'> {
  variant?: 'primary' | 'secondary' | 'ghost' | 'text' | 'danger';
  size?: 'small' | 'medium' | 'large';
  loading?: boolean;
  startIcon?: React.ReactNode;
  endIcon?: React.ReactNode;
  fullWidth?: boolean;
}
```

## IconButton

```ts
interface IconButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  label: string;
  icon: React.ReactNode;
  size?: 'small' | 'medium' | 'large';
  selected?: boolean;
  tooltip?: string;
}
```

## Panel

```ts
interface PanelProps {
  id: string;
  label: string;
  mode?: 'rail' | 'compact' | 'default' | 'expanded';
  header: React.ReactNode;
  children: React.ReactNode;
  footer?: React.ReactNode;
}
```

## ContextListItem

```ts
interface ContextListItemProps {
  id: string;
  title: string;
  metadata?: string;
  icon?: React.ReactNode;
  selected: boolean;
  status: 'ready' | 'processing' | 'failed' | 'unavailable';
  onSelectChange: (selected: boolean) => void;
  onOpen: () => void;
  onMenuOpen?: () => void;
}
```

## OutputCard

```ts
interface OutputCardProps {
  id: string;
  type: string;
  title: string;
  description?: string;
  status: 'queued' | 'generating' | 'ready' | 'failed';
  updatedAt?: string;
  progress?: number;
  onOpen: () => void;
  onRetry?: () => void;
  onStop?: () => void;
  onMenuOpen?: () => void;
}
```

## Composer

```ts
interface ComposerProps {
  value: string;
  contextLabel?: string;
  placeholder?: string;
  state: 'idle' | 'submitting' | 'generating' | 'disabled' | 'error';
  errorMessage?: string;
  suggestions?: Array<{
    id: string;
    label: string;
    value: string;
  }>;
  onChange: (value: string) => void;
  onSubmit: () => void;
  onStop?: () => void;
  onSuggestionSelect?: (value: string) => void;
}
```

## Citation

```ts
interface CitationProps {
  index: number;
  title: string;
  excerpt: string;
  location?: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onNavigate: () => void;
}
```

## EmptyState

```ts
interface EmptyStateProps {
  icon?: React.ReactNode;
  title: string;
  description: string;
  action?: {
    label: string;
    onClick: () => void;
  };
  secondaryAction?: {
    label: string;
    onClick: () => void;
  };
}
```

## StatusMessage

```ts
interface StatusMessageProps {
  tone: 'neutral' | 'info' | 'success' | 'warning' | 'danger';
  title: string;
  description?: string;
  action?: React.ReactNode;
  compact?: boolean;
}
```
