import * as React from "react";
import { cn } from "../../lib/utils";

interface DrawerContextValue {
  open: boolean;
  setOpen: (nextOpen: boolean) => void;
  titleId: string;
  descriptionId: string;
  triggerRef: React.MutableRefObject<HTMLElement | null>;
}

const DrawerContext = React.createContext<DrawerContextValue | null>(null);

function useDrawerContext(): DrawerContextValue {
  const ctx = React.useContext(DrawerContext);
  if (!ctx) {
    throw new Error("Drawer components must be used inside <Drawer />.");
  }
  return ctx;
}

export interface DrawerProps {
  open?: boolean;
  defaultOpen?: boolean;
  onOpenChange?: (open: boolean) => void;
  children: React.ReactNode;
}

/**
 * Container principal de Drawer (Bottom Sheet) compatível com a API do Shadcn UI.
 */
export function Drawer({
  open: controlledOpen,
  defaultOpen = false,
  onOpenChange,
  children,
}: DrawerProps) {
  const [uncontrolledOpen, setUncontrolledOpen] = React.useState(defaultOpen);
  const isControlled = controlledOpen !== undefined;
  const open = isControlled ? controlledOpen : uncontrolledOpen;

  const titleId = React.useId();
  const descriptionId = React.useId();
  const triggerRef = React.useRef<HTMLElement | null>(null);

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

    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.stopPropagation();
        setOpen(false);
        triggerRef.current?.focus();
      }
    };

    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.body.style.overflow = previousOverflow;
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [open, setOpen]);

  return (
    <DrawerContext.Provider
      value={{ open, setOpen, titleId, descriptionId, triggerRef }}
    >
      {children}
    </DrawerContext.Provider>
  );
}

export interface DrawerTriggerProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  asChild?: boolean;
}

/**
 * Gatilho de abertura do Drawer compatível com `asChild`.
 */
export const DrawerTrigger = React.forwardRef<
  HTMLButtonElement,
  DrawerTriggerProps
>(({ asChild = false, children, onClick, ...props }, forwardedRef) => {
  const { open, setOpen, triggerRef } = useDrawerContext();

  const assignRef = (node: HTMLElement | null) => {
    triggerRef.current = node;
    if (typeof forwardedRef === "function") {
      forwardedRef(node as HTMLButtonElement | null);
    } else if (forwardedRef) {
      forwardedRef.current = node as HTMLButtonElement | null;
    }
  };

  const handleOpen = (event: React.MouseEvent<HTMLElement>) => {
    onClick?.(event as React.MouseEvent<HTMLButtonElement>);
    if (!event.defaultPrevented) {
      setOpen(true);
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
      "aria-haspopup": "dialog",
      onClick: (event: React.MouseEvent<HTMLElement>) => {
        childOnClick?.(event);
        handleOpen(event);
      },
    });
  }

  return (
    <button
      ref={assignRef}
      type="button"
      aria-expanded={open}
      aria-haspopup="dialog"
      onClick={handleOpen}
      {...props}
    >
      {children}
    </button>
  );
});

DrawerTrigger.displayName = "DrawerTrigger";

export type DrawerContentProps = React.HTMLAttributes<HTMLDivElement>;

/**
 * Painel inferior (Bottom Sheet) do Drawer renderizado sobre backdrop escuro.
 */
export const DrawerContent = React.forwardRef<HTMLDivElement, DrawerContentProps>(
  ({ className, children, ...props }, ref) => {
    const { open, setOpen, titleId, descriptionId, triggerRef } =
      useDrawerContext();

    if (!open) return null;

    const handleClose = () => {
      setOpen(false);
      triggerRef.current?.focus();
    };

    return (
      <div className="fixed inset-0 z-50 flex items-end justify-center">
        <div
          aria-hidden="true"
          onClick={handleClose}
          className="fixed inset-0 bg-black/45 backdrop-blur-[1px]"
        />

        <div
          ref={ref}
          role="dialog"
          aria-modal="true"
          aria-labelledby={titleId}
          aria-describedby={descriptionId}
          className={cn(
            "relative z-10 max-h-[85dvh] w-full max-w-md overflow-y-auto rounded-t-3xl border-t border-[#E6E4DA] bg-[#F7F6F0] px-5 pb-6 pt-3 shadow-2xl",
            className
          )}
          {...props}
        >
          <div className="mb-3 flex items-center justify-between">
            <span className="h-8 w-8" aria-hidden="true" />
            <div
              aria-hidden="true"
              className="h-1.5 w-12 rounded-full bg-[#D5D1C5]"
            />
            <span className="h-8 w-8" aria-hidden="true" />
          </div>

          {children}
        </div>
      </div>
    );
  }
);

DrawerContent.displayName = "DrawerContent";

export type DrawerHeaderProps = React.HTMLAttributes<HTMLDivElement>;

/**
 * Cabeçalho estrutural do Drawer.
 */
export function DrawerHeader({ className, ...props }: DrawerHeaderProps) {
  return (
    <div className={cn("flex flex-col gap-1.5 text-left", className)} {...props} />
  );
}

export type DrawerTitleProps = React.HTMLAttributes<HTMLHeadingElement>;

/**
 * Título acessível do Drawer vinculado via `aria-labelledby`.
 */
export const DrawerTitle = React.forwardRef<
  HTMLHeadingElement,
  DrawerTitleProps
>(({ className, ...props }, ref) => {
  const { titleId } = useDrawerContext();

  return (
    <h2
      ref={ref}
      id={titleId}
      className={cn(
        "text-xl font-bold leading-snug tracking-tight text-[#511D4E]",
        className
      )}
      {...props}
    />
  );
});

DrawerTitle.displayName = "DrawerTitle";

export type DrawerDescriptionProps = React.HTMLAttributes<HTMLParagraphElement>;

/**
 * Texto descritivo do Drawer vinculado via `aria-describedby`.
 */
export const DrawerDescription = React.forwardRef<
  HTMLParagraphElement,
  DrawerDescriptionProps
>(({ className, ...props }, ref) => {
  const { descriptionId } = useDrawerContext();

  return (
    <p
      ref={ref}
      id={descriptionId}
      className={cn("text-sm leading-relaxed text-[#6D6960]", className)}
      {...props}
    />
  );
});

DrawerDescription.displayName = "DrawerDescription";

export type DrawerFooterProps = React.HTMLAttributes<HTMLDivElement>;

/**
 * Rodapé do Drawer para ações de fechamento ou confirmação.
 */
export function DrawerFooter({ className, ...props }: DrawerFooterProps) {
  return <div className={cn("mt-5 flex flex-col gap-2", className)} {...props} />;
}

export interface DrawerCloseProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  asChild?: boolean;
}

/**
 * Botão para fechar o Drawer compatível com `asChild`.
 */
export const DrawerClose = React.forwardRef<HTMLButtonElement, DrawerCloseProps>(
  ({ asChild = false, children, onClick, ...props }, ref) => {
    const { setOpen, triggerRef } = useDrawerContext();

    const handleClose = (event: React.MouseEvent<HTMLElement>) => {
      onClick?.(event as React.MouseEvent<HTMLButtonElement>);
      if (!event.defaultPrevented) {
        setOpen(false);
        triggerRef.current?.focus();
      }
    };

    if (
      asChild &&
      React.isValidElement<React.HTMLAttributes<HTMLElement>>(children)
    ) {
      const childOnClick = children.props.onClick;
      return React.cloneElement(children, {
        ...props,
        onClick: (event: React.MouseEvent<HTMLElement>) => {
          childOnClick?.(event);
          handleClose(event);
        },
      });
    }

    return (
      <button ref={ref} type="button" onClick={handleClose} {...props}>
        {children}
      </button>
    );
  }
);

DrawerClose.displayName = "DrawerClose";

