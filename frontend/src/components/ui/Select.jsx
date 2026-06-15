import * as RadixSelect from "@radix-ui/react-select";
import { Check, ChevronDown, ChevronUp } from "lucide-react";
import { clsx } from "clsx";

/**
 * Styled dropdown that matches the app's input UI.
 * Drop-in replacement for <select>.
 *
 * Usage:
 *   <Select
 *     value={value}
 *     onChange={setValue}
 *     placeholder="— Select —"
 *     options={[{value: "a", label: "Option A"}, ...]}
 *     size="md"   // "md" (default) | "sm"
 *     allowClear  // shows a "— None —" option that maps to null
 *     invalid     // red border when set
 *   />
 */
export default function Select({
  value,
  onChange,
  options,
  placeholder = "— Select —",
  size = "md",
  allowClear = false,
  invalid = false,
  disabled = false,
  className,
}) {
  const triggerCls = clsx(
    "inline-flex items-center justify-between gap-2 rounded-lg border bg-white text-left transition-colors focus:outline-none focus:ring-2 focus:ring-brand-500/20",
    size === "sm"
      ? "text-xs px-2.5 py-1"
      : "text-sm px-3 py-2 w-full",
    invalid ? "border-red-300 focus:border-red-500" : "border-slate-300 focus:border-brand-500",
    disabled && "opacity-50 cursor-not-allowed bg-slate-50",
    !disabled && "cursor-pointer hover:border-slate-400",
    className,
  );

  return (
    <RadixSelect.Root
      value={value || ""}
      onValueChange={(v) => onChange?.(v === "__none__" ? null : v)}
      disabled={disabled}
    >
      <RadixSelect.Trigger className={triggerCls} aria-label={placeholder}>
        <RadixSelect.Value placeholder={<span className="text-slate-400">{placeholder}</span>}>
          {/* Show the option's label, not its raw value */}
          {value ? (options.find((o) => o.value === value)?.label ?? value) : null}
        </RadixSelect.Value>
        <RadixSelect.Icon>
          <ChevronDown size={size === "sm" ? 13 : 16} className="text-slate-500" />
        </RadixSelect.Icon>
      </RadixSelect.Trigger>

      <RadixSelect.Portal>
        <RadixSelect.Content
          className="z-50 overflow-hidden bg-white rounded-lg border border-slate-200 shadow-lg min-w-[var(--radix-select-trigger-width)]"
          position="popper"
          sideOffset={4}
        >
          <RadixSelect.ScrollUpButton className="flex items-center justify-center py-1 bg-white text-slate-400">
            <ChevronUp size={14} />
          </RadixSelect.ScrollUpButton>

          <RadixSelect.Viewport className="p-1 max-h-[280px]">
            {allowClear && (
              <SelectItem value="__none__">
                <span className="text-slate-400 italic">— None —</span>
              </SelectItem>
            )}
            {options.map((opt) => (
              <SelectItem key={opt.value} value={opt.value} disabled={opt.disabled}>
                {opt.label}
              </SelectItem>
            ))}
          </RadixSelect.Viewport>

          <RadixSelect.ScrollDownButton className="flex items-center justify-center py-1 bg-white text-slate-400">
            <ChevronDown size={14} />
          </RadixSelect.ScrollDownButton>
        </RadixSelect.Content>
      </RadixSelect.Portal>
    </RadixSelect.Root>
  );
}

function SelectItem({ children, value, disabled }) {
  return (
    <RadixSelect.Item
      value={value}
      disabled={disabled}
      className={clsx(
        "relative flex items-center pl-7 pr-3 py-1.5 text-sm rounded-md select-none cursor-pointer outline-none",
        "text-slate-700",
        "data-[highlighted]:bg-brand-50 data-[highlighted]:text-brand-700",
        "data-[state=checked]:font-medium",
        "data-[disabled]:opacity-50 data-[disabled]:cursor-not-allowed",
      )}
    >
      <RadixSelect.ItemIndicator className="absolute left-2 inline-flex items-center">
        <Check size={13} className="text-brand-600" />
      </RadixSelect.ItemIndicator>
      <RadixSelect.ItemText>{children}</RadixSelect.ItemText>
    </RadixSelect.Item>
  );
}
