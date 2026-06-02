// app/supabase-auth.js
(function () {
    let supabaseClient = null;
    let bypassAuth = false;
    let configPromise = null;

    // Fetch config and initialize Supabase
    async function loadConfig() {
        if (configPromise) return configPromise;
        
        configPromise = (async () => {
            try {
                const response = await fetch('/api/config');
                if (!response.ok) throw new Error("Failed to fetch credentials from /api/config");
                const data = await response.json();
                
                if (!data.supabaseUrl || !data.supabaseAnonKey) {
                    console.warn("Supabase credentials not configured in backend .env. Operating in bypass/development mode.");
                    bypassAuth = true;
                    window.bypassAuth = true;
                    return null;
                }
                
                if (typeof supabase === 'undefined') {
                    console.error("Supabase JS SDK failed to load. Please verify CDN script tag.");
                    bypassAuth = true;
                    window.bypassAuth = true;
                    return null;
                }

                supabaseClient = supabase.createClient(data.supabaseUrl, data.supabaseAnonKey);
                window.supabaseClient = supabaseClient;
                return supabaseClient;
            } catch (err) {
                console.error("Error loading Supabase config:", err);
                bypassAuth = true;
                window.bypassAuth = true;
                return null;
            }
        })();
        
        return configPromise;
    }

    // Expose helpers globally
    window.FinSenseAuth = {
        init: loadConfig,
        
        getClient: async () => {
            await loadConfig();
            return supabaseClient;
        },
        
        isBypassMode: () => bypassAuth,

        getSession: async () => {
            await loadConfig();
            if (bypassAuth) {
                return {
                    access_token: "dev-token",
                    user: {
                        email: "dev@finsense.ai",
                        user_metadata: {}
                    }
                };
            }
            const { data, error } = await supabaseClient.auth.getSession();
            if (error || !data) return null;
            return data.session;
        },

        signInWithGoogle: async () => {
            await loadConfig();
            if (bypassAuth) {
                alert("Auth is bypassed in local development mode. Redirecting to dashboard...");
                window.location.href = 'index.html';
                return;
            }
            const { error } = await supabaseClient.auth.signInWithOAuth({
                provider: 'google',
                options: {
                    redirectTo: window.location.origin + '/index.html'
                }
            });
            if (error) throw error;
        },

        signInWithEmail: async (email, password) => {
            await loadConfig();
            if (bypassAuth) {
                // Mock success
                return {
                    user: { email, user_metadata: {} }
                };
            }
            const { data, error } = await supabaseClient.auth.signInWithPassword({
                email,
                password
            });
            if (error) throw error;
            return data;
        },

        signUpWithEmail: async (email, password, fullName) => {
            await loadConfig();
            if (bypassAuth) {
                // Mock success
                return {
                    user: { email, user_metadata: { full_name: fullName } }
                };
            }
            const { data, error } = await supabaseClient.auth.signUp({
                email,
                password,
                options: {
                    data: {
                        full_name: fullName
                    }
                }
            });
            if (error) throw error;
            return data;
        },

        signOut: async () => {
            await loadConfig();
            if (bypassAuth) {
                window.location.href = 'landing.html';
                return;
            }
            await supabaseClient.auth.signOut();
            window.location.href = 'landing.html';
        },

        resetPasswordForEmail: async (email) => {
            await loadConfig();
            if (bypassAuth) {
                alert("Auth is bypassed in local development mode. Simulating reset link sent to: " + email);
                return;
            }
            const { error } = await supabaseClient.auth.resetPasswordForEmail(email, {
                redirectTo: window.location.origin + '/reset-password.html'
            });
            if (error) throw error;
        },

        updatePassword: async (newPassword) => {
            await loadConfig();
            if (bypassAuth) {
                alert("Auth is bypassed in local development mode. Simulating password update...");
                return;
            }
            const { error } = await supabaseClient.auth.updateUser({
                password: newPassword
            });
            if (error) throw error;
        },

        checkAuthAndRedirect: async (pageType) => {
            await loadConfig();
            const session = await window.FinSenseAuth.getSession();
            const hasSession = !!session && (bypassAuth || !!session.access_token);

            if (pageType === 'protected') {
                if (!hasSession) {
                    console.log("Unauthenticated user on protected page. Redirecting to login.html.");
                    window.location.href = 'login.html';
                    return;
                }
                
                // Populate user profile info in the UI dynamically
                const user = session.user;
                const fullName = user.user_metadata?.full_name || user.email.split('@')[0];
                const email = user.email;
                const initials = fullName.split(' ').map(n => n[0]).join('').substring(0, 2).toUpperCase() || "US";
                
                // Update sidebars/headers across views
                document.querySelectorAll('[data-auth-initials]').forEach(el => el.textContent = initials);
                document.querySelectorAll('[data-auth-name]').forEach(el => el.textContent = fullName);
                document.querySelectorAll('[data-auth-email]').forEach(el => el.textContent = email);
                
                // Check if index.html's welcome greeting exists
                const greetingEl = document.getElementById('greeting-text');
                if (greetingEl) {
                    const now = new Date();
                    const hours = now.getHours();
                    let greeting = "Good morning";
                    if (hours >= 12 && hours < 17) greeting = "Good afternoon";
                    else greeting = "Good evening";
                    
                    greetingEl.innerText = `${greeting}, ${fullName}`;
                }
            } else if (pageType === 'guest') {
                if (hasSession && !bypassAuth) {
                    console.log("Authenticated user on guest/auth page. Redirecting to index.html.");
                    window.location.href = 'index.html';
                }
            }
        }
    };

    // Auto-initialize
    loadConfig();
})();
