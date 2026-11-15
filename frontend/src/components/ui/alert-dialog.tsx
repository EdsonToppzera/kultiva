import * as React from "react";
import { cn } from "../../lib/utils";
import { buttonVariants } from "./button";

interface AlertDialogContextValue {
  open: boolean;
  setOpen: (nextOpen: boolean) => void;
  titleId: string;
  descriptionId: string;
}

const AlertDialogContext =
  React.createContext<AlertDialogContextValue | null>(null);

function useAlertDialogContext(): AlertDialogContextValue {
  const ctx = React.useContext(AlertDialogContext);
  if (!ctx) {
    throw new Error(
      "AlertDialog components must be used inside <AlertDialog />."
    );
  }
  return ctx;
}

export interface AlertDialogProps {
  open?: boolean;
  defaultOpen?: boolean;
  onOpenChange?: (open: boolean) => void;
  children: React.ReactNode;
}

/**
 * Container de diálogo de confirmação bloqueante compatível com a API do Shadcn UI AlertDialog.
 */
export function AlertDialog({
  open: controlledOpen,
  defaultOpen = false,
  onOpenChange,
  children,
}: AlertDialogProps) {
  const [uncontrolledOpen, setUncontrolledOpen] = React.useState(defaultOpen);
  const isControlled = controlledOpen !== undefined;
  const open = isControlled ? controlledOpen : uncontrolledOpen;

  const titleId = React.useId();
  const descriptionId = React.useId();

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
      }
    };

    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.body.style.overflow = previousOverflow;
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [open, setOpen]);

  return (
    <AlertDialogContext.Provider
      value={{ open, setOpen, titleId, descriptionId }}
    >
      {children}
    </AlertDialogContext.Provider>
  );
}

export interface AlertDialogTriggerProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  asChild?: boolean;
}

/**
 * Gatilho de abertura do AlertDialog.
 */
export const AlertDialogTrigger = React.forwardRef<
  HTMLButtonElement,
  AlertDialogTriggerProps
>(({ asChild = false, children, onClick, ...props }, ref) => {
  const { setOpen } = useAlertDialogContext();

  const handleOpen = (event: React.MouseEvent<HTMLElement>) => {
    onClick?.(event as React.MouseEvent<HTMLButtonElement>);
    if (!event.defaultPrevented) {
      setOpen(true);
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
        handleOpen(event);
      },
    });
  }

  return (
    <button ref={ref} type="button" onClick={handleOpen} {...props}>
      {children}
    </button>
  );
});

AlertDialogTrigger.displayName = "AlertDialogTrigger";

export type AlertDialogContentProps = React.HTMLAttributes<HTMLDivElement>;

/**
 * Conteúdo centralizado do AlertDialog renderizado sobre overlay escuro.
 */
export const AlertDialogContent = React.forwardRef<
  HTMLDivElement,
  AlertDialogContentProps
>(({ className, children, ...props }, ref) => {
  const { open, titleId, descriptionId } = useAlertDialogContext();

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-5">
      <div
        aria-hidden="true"
        className="fixed inset-0 bg-black/50 backdrop-blur-[1px]"
      />

      <div
        ref={ref}
        role="alertdialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={descriptionId}
        className={cn(
          "relative z-10 w-full max-w-sm rounded-3xl border border-[#E6E4DA] bg-white p-6 shadow-2xl",
          className
        )}
        {...props}
      >
        {children}
      </div>
    </div>
  );
});

AlertDialogContent.displayName = "AlertDialogContent";

export type AlertDialogHeaderProps = React.HTMLAttributes<HTMLDivElement>;

/**
 * Cabeçalho do AlertDialog.
 */
export function AlertDialogHeader({
  className,
  ...props
}: AlertDialogHeaderProps) {
  return (
    <div className={cn("flex flex-col gap-2 text-left", className)} {...props} />
  );
}

export type AlertDialogTitleProps = React.HTMLAttributes<HTMLHeadingElement>;

/**
 * Título acessível do AlertDialog.
 */
export const AlertDialogTitle = React.forwardRef<
  HTMLHeadingElement,
  AlertDialogTitleProps
>(({ className, ...props }, ref) => {
  const { titleId } = useAlertDialogContext();

  return (
    <h2
      ref={ref}
      id={titleId}
      className={cn("text-xl font-bold text-[#1F1C18]", className)}
      {...props}
    />
  );
});

AlertDialogTitle.displayName = "AlertDialogTitle";

export type AlertDialogDescriptionProps =
  React.HTMLAttributes<HTMLParagraphElement>;

/**
 * Descrição acessível do AlertDialog.
 */
export const AlertDialogDescription = React.forwardRef<
  HTMLParagraphElement,
  AlertDialogDescriptionProps
>(({ className, ...props }, ref) => {
  const { descriptionId } = useAlertDialogContext();

  return (
    <p
      ref={ref}
      id={descriptionId}
      className={cn("text-sm leading-relaxed text-[#6D6960]", className)}
      {...props}
    />
  );
});

AlertDialogDescription.displayName = "AlertDialogDescription";

export type AlertDialogFooterProps = React.HTMLAttributes<HTMLDivElement>;

/**
 * Rodapé do AlertDialog para botões de ação lado a lado.
 */
export function AlertDialogFooter({
  className,
  ...props
}: AlertDialogFooterProps) {
  return (
    <div
      className={cn("mt-6 grid grid-cols-2 gap-3", className)}
      {...props}
    />
  );
}

export type AlertDialogActionProps =
  React.ButtonHTMLAttributes<HTMLButtonElement>;

/**
 * Botão de confirmação da ação do AlertDialog.
 */
export const AlertDialogAction = React.forwardRef<
  HTMLButtonElement,
  AlertDialogActionProps
>(({ className, onClick, ...props }, ref) => {
  const { setOpen } = useAlertDialogContext();

  return (
    <button
      ref={ref}
      type="button"
      onClick={(event) => {
        onClick?.(event);
        if (!event.defaultPrevented) {
          setOpen(false);
        }
      }}
      className={cn(
        buttonVariants({ variant: "destructive" }),
        "min-h-[48px] w-full rounded-xl px-4 text-sm font-semibold",
        className
      )}
      {...props}
    />
  );
});

AlertDialogAction.displayName = "AlertDialogAction";

export type AlertDialogCancelProps =
  React.ButtonHTMLAttributes<HTMLButtonElement>;

/**
 * Botão de cancelamento que fecha o AlertDialog.
 */
export const AlertDialogCancel = React.forwardRef<
  HTMLButtonElement,
  AlertDialogCancelProps
>(({ className, onClick, ...props }, ref) => {
  const { setOpen } = useAlertDialogContext();

  return (
    <button
      ref={ref}
      type="button"
      onClick={(event) => {
        onClick?.(event);
        if (!event.defaultPrevented) {
          setOpen(false);
        }
      }}
      className={cn(
        buttonVariants({ variant: "outline" }),
        "min-h-[48px] w-full rounded-xl border-0 bg-[#F3F2EC] px-4 text-sm font-semibold text-[#1F1C18] hover:bg-[#E7E5DC]",
        className
      )}
      {...props}
    />
  );
});

AlertDialogCancel.displayName = "AlertDialogCancel";

