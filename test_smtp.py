import asyncio
from app.email_utils import send_email, get_verification_email_template

async def test_smtp():
    print("🔧 Testing SMTP Configuration...")
    print("=" * 50)
    
    # Send to yourself for testing
    test_email = "beupintech@gmail.com"
    
    # Create test verification link
    verification_link = "http://localhost:3000/verify-email?token=test123abc456def"
    html_content = get_verification_email_template(verification_link, test_email)
    
    print(f"Sending test email to: {test_email}")
    print("Please wait...")
    
    try:
        result = await send_email(
            to_email=test_email,
            subject="✅ Test Email - Quran App Email Verification",
            html_content=html_content
        )
        
        if result:
            print("\n✅ SUCCESS! Email sent successfully!")
            print(f"Check inbox: {test_email}")
            print("\nIf you don't see it:")
            print("  1. Check your Spam/Junk folder")
            print("  2. Wait a few minutes")
            print("  3. Check the email address is correct")
        else:
            print("\n❌ FAILED! Email could not be sent.")
            print("Check your SMTP settings in .env file")
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        print("\nCommon issues:")
        print("  1. Wrong App Password - regenerate it")
        print("  2. 2FA not enabled on Gmail")
        print("  3. Network/firewall blocking SMTP")

if __name__ == "__main__":
    asyncio.run(test_smtp())