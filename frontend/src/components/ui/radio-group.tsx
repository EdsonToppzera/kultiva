import * as React from "react";
import { cn } from "../../lib/utils";

interface RadioGroupContextValue {
  value: string | null;
  onValueChange?: (value: string) => void;
  disabled?: boolean;
  groupRef: React.MutableRefObject<HTMLDivElement | null>;
}

const RadioGroupContext = React.createContext<RadioGroupContextValue | null>(
  null
);

function useRadioGroupContext(): RadioGroupContextValue {
  const ctx = React.useContext(RadioGroupContext);
  if (!ctx) {
    throw new Error("RadioGroupItem must be used inside <RadioGroup />.");
  }
  return ctx;
}

export interface RadioGroupProps
  extends Omit<React.HTMLAttributes<HTMLDivElement>, "onChange" | "defaultValue"> {
  value?: string | null;
  defaultValue?: string | null;
  onValueChange?: (value: string) => void;
  disabled?: boolean;
}

/**
 * Grupo acessível de seleção única compatível com a API do Shadcn UI RadioGroup.
 */
export const RadioGroup = React.forwardRef<HTMLDivElement, RadioGroupProps>(
  (
    {
      className,
      value: controlledValue,
      defaultValue = null,
      onValueChange,
      disabled = false,
      onKeyDown,
      children,
      ...props
    },
    forwardedRef
  ) => {
    const [uncontrolledValue, setUncontrolledValue] = React.useState<
      string | null
    >(defaultValue);
    const groupRef = React.useRef<HTMLDivElement | null>(null);

    const isControlled = controlledValue !== undefined;
    const value = isControlled ? controlledValue : uncontrolledValue;

    const handleValueChange = React.useCallback(
      (nextValue: string) => {
        if (!isControlled) {
          setUncontrolledValue(nextValue);
        }
        onValueChange?.(nextValue);
      },
      [isControlled, onValueChange]
    );

    const assignRef = (node: HTMLDivElement | null) => {
      groupRef.current = node;
      if (typeof forwardedRef === "function") {
        forwardedRef(node);
      } else if (forwardedRef) {
        forwardedRef.current = node;
      }
    };

    const handleKeyDown = (event: React.KeyboardEvent<HTMLDivElement>) => {
      onKeyDown?.(event);
      if (event.defaultPrevented || disabled) return;

      const keys = ["ArrowDown", "ArrowRight", "ArrowUp", "ArrowLeft"];
      if (!keys.includes(event.key)) return;

      const items = Array.from(
        groupRef.current?.querySelectorAll<HTMLButtonElement>(
          '[role="radio"]:not([disabled])'
        ) ?? []
      );
      if (items.length === 0) return;

      event.preventDefault();
      const activeElement = document.activeElement as HTMLButtonElement | null;
      const currentIndex = items.indexOf(activeElement as HTMLButtonElement);
      const step =
        event.key === "ArrowDown" || event.key === "ArrowRight" ? 1 : -1;
      const nextIndex =
        currentIndex === -1
          ? 0
          : (currentIndex + step + items.length) % items.length;

      const nextItem = items[nextIndex];
      nextItem.focus();
      const nextVal = nextItem.dataset.value;
      if (nextVal !== undefined) {
        handleValueChange(nextVal);
      }
    };

    return (
      <RadioGroupContext.Provider
        value={{ value, onValueChange: handleValueChange, disabled, groupRef }}
      >
        <div
          ref={assignRef}
          role="radiogroup"
          onKeyDown={handleKeyDown}
          className={cn("flex flex-col gap-3", className)}
          {...props}
        >
          {children}
        </div>
      </RadioGroupContext.Provider>
    );
  }
);

RadioGroup.displayName = "RadioGroup";

export interface RadioGroupItemProps
  extends Omit<
    React.ButtonHTMLAttributes<HTMLButtonElement>,
    "value" | "children"
  > {
  value: string;
  children?:
    | React.ReactNode
    | ((state: { checked: boolean }) => React.ReactNode);
}

/**
 * Item selecionável de um RadioGroup com gerenciamento de estado `aria-checked` e foco por teclado.
 */
export const RadioGroupItem = React.forwardRef<
  HTMLButtonElement,
  RadioGroupItemProps
>(({ className, value, disabled, onClick, children, ...props }, ref) => {
  const {
    value: selectedValue,
    onValueChange,
    disabled: groupDisabled,
    groupRef,
  } = useRadioGroupContext();

  const isChecked = selectedValue === value;
  const isDisabled = Boolean(disabled || groupDisabled);
  const [isFirstFallback, setIsFirstFallback] = React.useState(false);

  React.useLayoutEffect(() => {
    if (selectedValue !== null) {
      setIsFirstFallback(false);
      return;
    }
    const firstRadio = groupRef.current?.querySelector<HTMLButtonElement>(
      '[role="radio"]:not([disabled])'
    );
    setIsFirstFallback(firstRadio?.dataset.value === value);
  }, [groupRef, selectedValue, value]);

  return (
    <button
      ref={ref}
      type="button"
      role="radio"
      aria-checked={isChecked}
      data-state={isChecked ? "checked" : "unchecked"}
      data-value={value}
      disabled={isDisabled}
      tabIndex={isChecked || isFirstFallback ? 0 : -1}
      onClick={(event) => {
        onClick?.(event);
        if (!event.defaultPrevented && !isDisabled) {
          onValueChange?.(value);
        }
      }}
      className={cn(
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#511D4E] focus-visible:ring-offset-2 focus-visible:ring-offset-[#F7F6F0]",
        "disabled:pointer-events-none disabled:opacity-50",
        className
      )}
      {...props}
    >
      {typeof children === "function"
        ? children({ checked: isChecked })
        : children}
    </button>
  );
});

RadioGroupItem.displayName = "RadioGroupItem";
