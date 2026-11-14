import * as React from "react";
import { cn } from "../../lib/utils";

interface PopoverContextValue {
  open: boolean;
  setOpen: (nextOpen: boolean) => void;
  contentId: string;
  triggerRef: React.MutableRefObject<HTMLElement | null>;
}

const PopoverContext = React.createContext<PopoverContextValue | null>(null);

function usePopoverContext(): PopoverContextValue {
  const ctx = React.useContext(PopoverContext);
  if (!ctx) {
    throw new Error("Popover components must be used inside <Popover />.");
  }
  return ctx;
}

export interface PopoverProps {
  open?: boolean;
  defaultOpen?: boolean;
  onOpenChange?: (open: boolean) => void;
  children: React.ReactNode;
  className?: string;
}

/**
 * Container principal de Popover compatível com a API do Shadcn UI.
 */
export function Popover({
  open: controlledOpen,
  defaultOpen = false,
  onOpenChange,
  children,
  className,
}: PopoverProps) {
  const [uncontrolledOpen, setUncontrolledOpen] = React.useState(defaultOpen);
  const isControlled = controlledOpen !== undefined;
  const open = isControlled ? controlledOpen : uncontrolledOpen;
  const rootRef = React.useRef<HTMLDivElement>(null);
  const triggerRef = React.useRef<HTMLElement | null>(null);
  const contentId = React.useId();

  const setOpen = React.useCallback(
    (nextOpen: boolean) => {
      if (!isControlled) {
        setUncontrolledOpen(nextOpen);
      }
      onOpenChange?.(nextOpen);
    },
    [isControlled, onOpenChange]
  );

  React.useEffect(() => {
    if (!open) return;

    const handlePointerDown = (event: PointerEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) {
        setOpen(false);
      }
    };

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.stopPropagation();
        setOpen(false);
        triggerRef.current?.focus();
      }
    };

    document.addEventListener("pointerdown", handlePointerDown);
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("pointerdown", handlePointerDown);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [open, setOpen]);

  return (
    <PopoverContext.Provider value={{ open, setOpen, contentId, triggerRef }}>
      <div ref={rootRef} className={cn("relative w-full", className)}>
        {children}
      </div>
    </PopoverContext.Provider>
  );
}

export interface PopoverTriggerProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  asChild?: boolean;
}

/**
 * Gatilho de abertura e fechamento do Popover compatível com `asChild`.
 */
export const PopoverTrigger = React.forwardRef<
  HTMLButtonElement,
  PopoverTriggerProps
>(({ asChild = false, children, onClick, ...props }, forwardedRef) => {
  const { open, setOpen, contentId, triggerRef } = usePopoverContext();

  const handleToggle = (event: React.MouseEvent<HTMLElement>) => {
    onClick?.(event as React.MouseEvent<HTMLButtonElement>);
    if (!event.defaultPrevented) {
      setOpen(!open);
    }
  };

  const assignRef = (node: HTMLElement | null) => {
    triggerRef.current = node;
    if (typeof forwardedRef === "function") {
      forwardedRef(node as HTMLButtonElement | null);
    } else if (forwardedRef) {
      forwardedRef.current = node as HTMLButtonElement | null;
    }
  };

  if (
    asChild &&
    React.isValidElement<
      React.HTMLAttributes<HTMLElement> & React.RefAttributes<HTMLElement>
    >(children)
  ) {
    const childOnClick = children.props.onClick;

    return React.cloneElement(children, {
      ...props,
      ref: assignRef,
      "aria-expanded": open,
      "aria-controls": contentId,
      "aria-haspopup": "dialog",
      onClick: (event: React.MouseEvent<HTMLElement>) => {
        childOnClick?.(event);
        handleToggle(event);
      },
    });
  }

  return (
    <button
      ref={assignRef}
      type="button"
      aria-expanded={open}
      aria-controls={contentId}
      aria-haspopup="dialog"
      onClick={handleToggle}
      {...props}
    >
      {children}
    </button>
  );
});

PopoverTrigger.displayName = "PopoverTrigger";

export interface PopoverContentProps
  extends React.HTMLAttributes<HTMLDivElement> {
  align?: "start" | "center" | "end";
  sideOffset?: number;
}

const ALIGN_CLASSES: Record<NonNullable<PopoverContentProps["align"]>, string> = {
  start: "left-0",
  center: "left-1/2 -translate-x-1/2",
  end: "right-0",
};

/**
 * Superfície flutuante do Popover renderizada quando aberta.
 */
export const PopoverContent = React.forwardRef<
  HTMLDivElement,
  PopoverContentProps
>(({ className, align = "start", sideOffset = 8, style, children, ...props }, ref) => {
  const { open, contentId } = usePopoverContext();

  if (!open) return null;

  return (
    <div
      ref={ref}
      id={contentId}
      role="dialog"
      style={{ marginTop: sideOffset, ...style }}
      className={cn(
        "absolute top-full z-50 w-full rounded-2xl border border-[#511D4E]/25 bg-[#F7F6F0] p-2 shadow-xl shadow-[#511D4E]/10",
        ALIGN_CLASSES[align],
        className
      )}
      {...props}
    >
      {children}
    </div>
  );
});

PopoverContent.displayName = "PopoverContent";
