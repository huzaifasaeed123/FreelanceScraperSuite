import vobject

# Function to extract information from a vCard file
def parse_vcf(file_path):
    with open(file_path, 'r') as vcf_file:
        vcard = vobject.readOne(vcf_file)

        # Extract Name
        if hasattr(vcard, 'fn'):
            name = vcard.fn.value
        else:
            name = 'No name found'
        
        # Extract Email
        if hasattr(vcard, 'email'):
            email = vcard.email.value
        else:
            email = 'No email found'

        # Extract Phone Number
        phone = ''
        if hasattr(vcard, 'tel_list'):
            for tel in vcard.tel_list:
                phone += tel.value + ' '

        if phone == '':
            phone = 'No phone number found'

        # Extract Position (usually in Title or Role)
        if hasattr(vcard, 'title'):
            position = vcard.title.value
        else:
            position = 'No position found'

        return {
            'Name': name,
            'Email': email,
            'Phone': phone.strip(),
            'Position': position
        }

# Provide the path to your VCF file
file_path = "appel-marco-1.vcf"

# Call the function and print the extracted data
vcard_info = parse_vcf(file_path)
print(vcard_info)
