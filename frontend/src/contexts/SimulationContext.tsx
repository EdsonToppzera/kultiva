import * as React from "react";

interface SimulationContextValue {
  isSimulationMode: boolean;
  cancelSimulation: (() => void) | null;
}

const SimulationContext = React.createContext<SimulationContextValue>({
  isSimulationMode: false,
  cancelSimulation: null,
});

export interface SimulationProviderProps {
  isSimulationMode: boolean;
  onCancelSimulation: () => void;
  children: React.ReactNode;
}

/**
 * Disponibiliza o estado e a ação de cancelar a simulação para todas as páginas do fluxo.
 */
export function SimulationProvider({
  isSimulationMode,
  onCancelSimulation,
  children,
}: SimulationProviderProps) {
  const value = React.useMemo<SimulationContextValue>(
    () => ({
      isSimulationMode,
      cancelSimulation: isSimulationMode ? onCancelSimulation : null,
    }),
    [isSimulationMode, onCancelSimulation]
  );

  return (
    <SimulationContext.Provider value={value}>
      {children}
    </SimulationContext.Provider>
  );
}

export function useSimulation(): SimulationContextValue {
  return React.useContext(SimulationContext);
}
