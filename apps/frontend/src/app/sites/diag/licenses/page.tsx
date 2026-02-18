"use client";

import { useState, FormEvent } from "react";
import { LicenseCheckService } from "@/api";
import LicenseWarning from "./licenseWarning";

// Type pour les données simulées
type LicenseAlert = {
  id: string;
  name: string;
  expiryDate: string;
  daysRemaining: number;
  periodicity: string;
  term: string;
  isTrial: boolean;
  seats: number;
  autoRenew: boolean;
};

async function handleLicenseCheck(reference: string) {
  try {
    const response = await LicenseCheckService.licensesSubmitCreate({ ref: reference });
    return response;
  } catch (error) {
    console.error("API Error:", error);
    return {};
  }
}

interface LicenseInfo {
  name: string;
  expiryDate: string;
  daysRemaining: number;
  periodicity: string;
  term: string;
  isTrial: boolean;
  seats: number;
  autoRenew: boolean;
}

interface LicenseResponse {
  [licenseId: string]: LicenseInfo;
}

export default function LicenseCheckPage() {
  const [companyName, setCompanyName] = useState("");
  const [refNumber, setRefNumber] = useState("");
  const [alerts, setAlerts] = useState<LicenseAlert[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [showExpired, setShowExpired] = useState(false); // État pour le menu déroulant des licences expirées

  // Validation du format XSP + 7 chiffres
  const validateRef = (ref: string) => /^XSP\d{7}$/.test(ref);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    setAlerts(null);
    setShowExpired(false); // Réinitialiser l'état du menu au lancement d'une nouvelle recherche

    if (!companyName.trim()) {
      setError("Le nom de l'entreprise est requis.");
      return;
    }

    if (!validateRef(refNumber)) {
      setError("Le numéro de référence doit commencer par 'XSP' suivi de 7 chiffres (ex: XSP1234567).");
      return;
    }

    setLoading(true);

    const data = (await handleLicenseCheck(refNumber)) as LicenseResponse;

    const finalAlerts: LicenseAlert[] = [];

    for (const licenseId in data) {
      const license = data[licenseId];
      finalAlerts.push({
        id: licenseId,
        name: license.name,
        expiryDate: license.expiryDate,
        daysRemaining: license.daysRemaining,
        periodicity: license.periodicity,
        term: license.term, // correction ici
        isTrial: license.isTrial,
        seats: license.seats,
        autoRenew: license.autoRenew,
      });
    }

    // Tri optionnel : les plus urgentes en premier
    finalAlerts.sort((a, b) => a.daysRemaining - b.daysRemaining);

    setAlerts(finalAlerts);
    setLoading(false);
  };

  // Séparation des alertes pour l'affichage
  const activeAlerts = alerts?.filter(a => a.daysRemaining > 0) || [];
  const expiredAlerts = alerts?.filter(a => a.daysRemaining <= 0) || [];

  return (
    <div className="min-h-screen flex items-center justify-center p-4">
      <div className="w-full max-w-2xl bg-gray-900/80 backdrop-blur-sm border border-gray-700 rounded-xl p-8 shadow-2xl">
        <h1 className="text-2xl font-bold text-white mb-6">
          Vérification des licences Microsoft
        </h1>

        <form onSubmit={handleSubmit} className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <label htmlFor="company" className="block text-sm font-medium text-gray-300 mb-2">
                Nom de l'entreprise
              </label>
              <input
                type="text"
                id="company"
                value={companyName}
                onChange={(e) => setCompanyName(e.target.value)}
                className="w-full px-4 py-2 bg-gray-800 border border-gray-600 rounded-lg text-white focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none transition"
                placeholder="Ex: Contoso Ltd"
              />
            </div>

            <div>
              <label htmlFor="ref" className="block text-sm font-medium text-gray-300 mb-2">
                Numéro de référence
              </label>
              <input
                type="text"
                id="ref"
                value={refNumber}
                onChange={(e) => setRefNumber(e.target.value.toUpperCase())}
                className="w-full px-4 py-2 bg-gray-800 border border-gray-600 rounded-lg text-white focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none transition"
                placeholder="XSP9999999"
                maxLength={10}
              />
            </div>
          </div>

          {error && (
            <div className="p-3 bg-red-900/50 border border-red-700 text-red-200 rounded-lg text-sm">
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full py-3 px-4 bg-blue-600 hover:bg-blue-700 text-white font-semibold rounded-lg shadow-md transition disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? "Recherche en cours..." : "Vérifier les expirations"}
          </button>
        </form>

        {alerts && (
          <div className="mt-8 space-y-6">
            <h2 className="text-xl font-semibold text-white border-b border-gray-700 pb-2">
              Résultats de l'analyse
            </h2>

            {alerts.length === 0 ? (
              <p className="text-green-400">Aucune licence trouvée pour ce dossier.</p>
            ) : (
              <>
                <div className="space-y-4">
                  {activeAlerts.length > 0 ? (
                    activeAlerts.map((alert) => (
                      <LicenseWarning
                        key={alert.id}
                        {...alert}
                        days_left={alert.daysRemaining}
                        title={alert.name}
                        expiry_date={alert.expiryDate}
                      />
                    ))
                  ) : (
                    expiredAlerts.length === 0 && <p className="text-gray-400 text-sm">Aucune licence active.</p>
                  )}
                </div>

                {expiredAlerts.length > 0 && (
                  <div className="mt-6 border-t border-gray-700 pt-4">
                    <button
                      onClick={() => setShowExpired(!showExpired)}
                      className="w-full flex items-center justify-between p-3 bg-red-900/10 border border-red-900/30 rounded-lg hover:bg-red-900/20 transition-colors group"
                    >
                      <div className="flex items-center gap-3">
                        <span className="flex items-center justify-center w-6 h-6 rounded-full bg-red-900/50 text-red-400 text-xs font-bold border border-red-800">
                          {expiredAlerts.length}
                        </span>
                        <span className="text-red-300 font-medium text-sm">
                          Licences expirées / Inactives
                        </span>
                      </div>
                      <svg
                        className={`text-red-400 transition-transform duration-200 ${showExpired ? 'rotate-180' : ''}`}
                        width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
                      >
                        <path d="M6 9l6 6 6-6"/>
                      </svg>
                    </button>

                    <div className={`transition-all duration-300 ease-in-out overflow-hidden ${showExpired ? 'max-h-[1000px] opacity-100 mt-4' : 'max-h-0 opacity-0'}`}>
                      <div className="space-y-4 pl-2 border-l-2 border-gray-800">
                        {expiredAlerts.map((alert) => (
                          <div key={alert.id} className="opacity-75 hover:opacity-100 transition-opacity">
                            <LicenseWarning
                              {...alert}
                              days_left={alert.daysRemaining}
                              title={alert.name}
                              expiry_date={alert.expiryDate}
                            />
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                )}
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
