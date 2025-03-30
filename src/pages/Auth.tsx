import { useState, useEffect } from 'react';
import { useNavigate, Link, useLocation } from 'react-router-dom';
import { useAuth } from '@/contexts/AuthContext';
import { Shield, ArrowRight, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { useToast } from '@/hooks/use-toast';

// Convert 'login', 'register', 'reset-password' to title case
const getPageTitle = (page: string) => {
  switch (page) {
    case 'login':
      return 'Log In';
    case 'register':
      return 'Register';
    case 'reset-password':
      return 'Reset Password';
    default:
      return 'Authentication';
  }
};

const Auth = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { user, signIn, signUp, resetPassword, loading } = useAuth();
  const { toast } = useToast();
  
  // Determine which auth screen to show based on URL
  const authType = location.pathname.split('/').pop() || 'login';
  
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [image, setImage] = useState<File | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // If user is already logged in, redirect to dashboard
  useEffect(() => {
    if (user && authType !== 'reset-password') {
      navigate('/dashboard');
    }
  }, [user, navigate, authType]);

  // Function to handle gender verification
  const verifyGender = async () => {
    if (!image) {
      toast({
        title: "Profile photo required",
        description: "Please upload a clear image for verification",
        variant: "destructive",
      });
      return false;
    }

    const formData = new FormData();
    formData.append("file", image);

    try {
      const response = await fetch("http://localhost:8000/predict", {
        method: "POST",
        body: formData,
      });

      const data = await response.json();

      if (data.gender !== "female") {
        toast({
          title: "Registration denied",
          description: "Only female users are allowed to register",
          variant: "destructive",
        });
        return false;
      }
      return true;
    } catch (error) {
      toast({
        title: "Error verifying gender",
        description: "There was an issue verifying your gender. Please try again.",
        variant: "destructive",
      });
      return false;
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (isSubmitting) return;

    setIsSubmitting(true);

    try {
      if (authType === 'register') {
        if (password !== confirmPassword) {
          toast({
            title: "Passwords don't match",
            description: "Please make sure your passwords match",
            variant: "destructive",
          });
          return;
        }

        if (password.length < 6) {
          toast({
            title: "Password too short",
            description: "Password must be at least 6 characters",
            variant: "destructive",
          });
          return;
        }

        // Verify gender before allowing registration
        const isFemale = await verifyGender();
        if (!isFemale) {
          setIsSubmitting(false);
          return;
        }

        await signUp(email, password);
        toast({
          title: "Account created",
          description: "Please check your email to confirm your account",
        });
      } else if (authType === 'login') {
        await signIn(email, password);
      } else if (authType === 'reset-password') {
        await resetPassword(email);
        toast({
          title: "Password reset email sent",
          description: "Please check your email for the reset link",
        });
      }
    } catch (error: any) {
      toast({
        title: "Authentication error",
        description: error.message || "An error occurred during authentication",
        variant: "destructive",
      });
    } finally {
      setIsSubmitting(false);
    }
  };
  
  return (
    <div className="min-h-screen flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        <div className="flex justify-center mb-6">
          <Link to="/" className="flex items-center space-x-2 text-foreground">
            <Shield className="h-10 w-10 text-primary" />
            <span className="text-2xl font-semibold">Silent Guardians</span>
          </Link>
        </div>
        
        <div className="bg-card rounded-xl shadow-lg p-8 border border-border">
          <h1 className="text-2xl font-medium mb-6">{getPageTitle(authType)}</h1>
          
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                type="email"
                placeholder="you@example.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                disabled={isSubmitting}
              />
            </div>
            
            {authType !== 'reset-password' && (
              <div className="space-y-2">
                <Label htmlFor="password">Password</Label>
                <Input
                  id="password"
                  type="password"
                  placeholder="••••••••"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  minLength={6}
                  disabled={isSubmitting}
                />
              </div>
            )}
            
            {authType === 'register' && (
              <>
                <div className="space-y-2">
                  <Label htmlFor="confirm-password">Confirm Password</Label>
                  <Input
                    id="confirm-password"
                    type="password"
                    placeholder="••••••••"
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    required
                    minLength={6}
                    disabled={isSubmitting}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="image">Upload Profile Photo (for verification)</Label>
                  <Input
                    id="image"
                    type="file"
                    accept="image/*"
                    onChange={(e) => setImage(e.target.files?.[0] || null)}
                    required
                  />
                </div>
              </>
            )}
            
            <Button type="submit" className="w-full" disabled={isSubmitting || loading}>
              {isSubmitting ? (
                <>
                  <Loader2 size={16} className="mr-2 animate-spin" />
                  Processing...
                </>
              ) : (
                <>
                  {authType === 'login' ? 'Log In' : 
                   authType === 'register' ? 'Create Account' : 'Send Reset Link'}
                  <ArrowRight size={16} className="ml-2" />
                </>
              )}
            </Button>
          </form>
        </div>
      </div>
    </div>
  );
};

export default Auth;